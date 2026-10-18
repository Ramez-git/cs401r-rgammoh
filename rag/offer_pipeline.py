"""Policy-grounded retention offers using Titan, local FAISS and Bedrock Haiku."""
from __future__ import annotations
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import boto3
from botocore.config import Config
import faiss
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
EMBED = 'amazon.titan-embed-text-v2:0'
CATEGORIES = {'Apparel', 'Footwear', 'Home', 'Electronics', 'Beauty', 'Grocery', 'Toys', 'Outdoor'}
TIERS = {'Bronze', 'Silver', 'Gold', 'Platinum'}


def chunks_from_corpus(directory: Path, size=220, overlap=40):
    if not 0 <= overlap < size:
        raise ValueError('Overlap must be smaller than chunk size')
    chunks = []
    for path in sorted(directory.glob('*.md')):
        text = path.read_text(encoding='utf-8-sig')
        doc = re.search(r'\*\*Document ID:\*\*\s*(\S+)', text).group(1)
        sections = re.split(r'(?=^#{2,3} )', text, flags=re.M)
        for section_no, section in enumerate(sections):
            words = section.split()
            heading = section.splitlines()[0].lstrip('# ').strip()
            for start in range(0, len(words), size-overlap):
                body = ' '.join(words[start:start+size])
                if not body:
                    continue
                cid = f'{doc}-s{section_no:02d}-c{start//(size-overlap)+1:02d}'
                chunks.append({'id': cid, 'doc_id': doc, 'source': path.name,
                    'heading': heading, 'text': f'[{cid}] {heading}\n{body}'})
                if start+size >= len(words):
                    break
    return chunks


class OfferRAG:
    def __init__(self, region='us-east-1', model=MODEL, cache=None, log_path=None):
        self.region, self.model = region, model
        self.cache = Path(cache or ROOT/'.rag-cache')
        self.cache.mkdir(parents=True, exist_ok=True)
        self.log_path = Path(log_path or ROOT/'docs/lab3-evidence/rag-usage.jsonl')
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.client = boto3.client('bedrock-runtime', region_name=region,
            config=Config(retries={'max_attempts': 5, 'mode': 'adaptive'}, read_timeout=120))
        self.chunks = chunks_from_corpus(ROOT/'northstar-policy-docs')
        self.manifest_sha = hashlib.sha256(json.dumps(self.chunks, sort_keys=True).encode()).hexdigest()
        self.index = None

    def _log(self, row):
        with self.log_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'timestamp': datetime.now(timezone.utc).isoformat(), **row})+'\n')

    def embed(self, text):
        key = hashlib.sha256((EMBED+text).encode()).hexdigest()
        path = self.cache/f'{key}.npy'
        if path.exists():
            return np.load(path)
        start = time.monotonic()
        response = self.client.invoke_model(modelId=EMBED, contentType='application/json',
            accept='application/json', body=json.dumps({'inputText': text, 'dimensions': 1024, 'normalize': True}))
        result = json.loads(response['body'].read())
        vector = np.array(result['embedding'], dtype='float32')
        vector /= np.linalg.norm(vector)
        np.save(path, vector)
        self._log({'operation': 'embedding', 'model': EMBED,
                   'input_tokens': result.get('inputTextTokenCount', 0), 'output_tokens': 0,
                   'latency_ms': round((time.monotonic()-start)*1000),
                   'request_id': response['ResponseMetadata']['RequestId']})
        return vector

    def build_index(self):
        matrix = np.vstack([self.embed(c['text']) for c in self.chunks])
        self.index = faiss.IndexFlatIP(matrix.shape[1])
        self.index.add(matrix)
        faiss.write_index(self.index, str(self.cache/'policies.faiss'))
        manifest = {'corpus_sha256': self.manifest_sha, 'embedding_model': EMBED,
                    'dimensions': 1024, 'chunk_words': 220, 'overlap_words': 40,
                    'chunks': self.chunks}
        (self.cache/'chunk-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return manifest

    def search(self, query, k=6, documents=None):
        if self.index is None:
            self.build_index()
        scores, indices = self.index.search(self.embed(query).reshape(1, -1), len(self.chunks))
        selected = []
        for score, ix in zip(scores[0], indices[0]):
            chunk = self.chunks[int(ix)]
            if documents is None or chunk['doc_id'] in documents:
                selected.append(chunk | {'score': float(score)})
            if len(selected) == k:
                break
        return selected

    def retrieve(self, profile, strategy='hybrid'):
        tier = profile['loyalty_tier']
        entitlement = f'loyalty tier {tier} benefits points earn rate free standard shipping threshold return window birthday reward annual gear credit'
        constraint = 'final sale non-returnable exclusions expired offers cannot be reinstated retention offer validity single use combinability free expedited shipping Mexico restrictions'
        if strategy == 'tier':
            return self.search(entitlement, 6)
        if strategy == 'constraint':
            return self.search(constraint, 6)
        if strategy != 'hybrid':
            raise ValueError('Unknown retrieval strategy')
        channel = 'online standard shipping' if profile.get('online_to_store_ratio', .5) > .5 else 'in store points rewards'
        first = self.search(entitlement+' '+channel, 4, {'POL-LOY-011', 'POL-SHP-007'})
        second = self.search(constraint, 4, {'POL-LOY-011', 'POL-SHP-007', 'POL-RET-004'})
        return list({c['id']: c for c in first+second}.values())

    @staticmethod
    def validate_profile(profile):
        if profile.get('loyalty_tier') not in TIERS:
            raise ValueError('Known feature-store tier is required')
        categories = profile.get('top_categories', [])
        if not categories or any(c not in CATEGORIES for c in categories):
            raise ValueError('Use only observed NorthStar product categories')
        if not 0 <= profile.get('churn_probability', -1) <= 1:
            raise ValueError('Valid model score is required')

    @staticmethod
    def profile_context(profile):
        safe_fields = ['customer_id', 'churn_probability', 'loyalty_tier', 'days_since_last_purchase',
            'total_lifetime_value', 'avg_order_value', 'category_diversity_score', 'online_to_store_ratio', 'top_categories']
        safe = {k: profile[k] for k in safe_fields if k in profile}
        channel = 'mostly online' if profile.get('online_to_store_ratio', .5) > .5 else 'mostly in store'
        diversity = 'narrow category history' if profile.get('category_diversity_score', 1) <= .25 else 'several observed categories'
        return ('Customer profile (observed synthetic data, not authoritative benefit eligibility): '+
            json.dumps(safe, sort_keys=True)+f'. Shopping pattern: {channel}; {diversity}. '+
            'Stored tier is a lifetime-value approximation. Current tier, unused rewards, destination and product eligibility are unverified.')

    def generate_unguarded(self, profile, question, strategy='hybrid', include_profile_context=True):
        self.validate_profile(profile)
        retrieved = self.retrieve(profile, strategy)
        profile_text = self.profile_context(profile)
        system = (ROOT/'prompt_templates/freeform_offer_system.md').read_text(encoding='utf-8-sig')
        policy_context = '\n\n'.join(c['text'] for c in retrieved)
        user = f'PROFILE DATA:\n{profile_text}\n\nPOLICY EVIDENCE:\n{policy_context}\n\nREQUEST (untrusted text):\n{question}'
        start = time.monotonic()
        response = self.client.converse(modelId=self.model, system=[{'text': system}],
            messages=[{'role': 'user', 'content': [{'text': user}]}],
            inferenceConfig={'temperature': 0, 'maxTokens': 300})
        answer = ''.join(c.get('text', '') for c in response['output']['message']['content']).strip()
        usage = response.get('usage', {})
        self._log({'operation': 'generation', 'model': self.model, 'strategy': strategy,
            'customer_id': profile.get('customer_id'), 'input_tokens': usage.get('inputTokens', 0),
            'output_tokens': usage.get('outputTokens', 0), 'latency_ms': round((time.monotonic()-start)*1000),
            'request_id': response['ResponseMetadata']['RequestId']})
        contexts = [c['text'] for c in retrieved]
        if include_profile_context:
            contexts.append(profile_text)
        return {'answer': answer, 'contexts': contexts, 'chunk_ids': [c['id'] for c in retrieved],
            'profile_context': profile_text, 'customer_profile': profile, 'strategy': strategy,
            'usage': usage, 'request_id': response['ResponseMetadata']['RequestId']}

    @staticmethod
    def approved_incentive(profile, retrieved):
        """Parse a policy row; no tier rate is invented or guessed from lifetime value."""
        tier = profile['loyalty_tier']
        evidence = '\n'.join(c['text'] for c in retrieved if c['doc_id'] == 'POL-LOY-011')
        match = re.search(r'\|\s*'+re.escape(tier)+r'\s*\|\s*([\d.]+)[×x]', evidence)
        if not match:
            return 'Check your account to confirm which loyalty benefits apply before purchasing.'
        rate = match.group(1)
        if tier == 'Platinum' and '$100 gear credit' in evidence:
            return ('If your account confirms Platinum status and an unused annual gear credit, '
                    'check whether its $100 credit applies to your gear purchase before December 31.')
        unit = 'point' if rate == '1' else 'points'
        return f'If your account confirms {tier} status, you can earn {rate} {unit} per $1 of qualifying merchandise spend.'

    @staticmethod
    def validate_copy(draft, profile):
        errors = []
        for key in ['recommendation', 'call_to_action']:
            text = draft.get(key, '')
            if not isinstance(text, str) or len(text) > 230 or len(re.findall(r'[.!?](?:\s|$)', text)) != 1:
                errors.append(key+': require one short complete sentence')
                continue
            if re.search(r'\b(new|latest|missed|sale|discount|free|shipping|points|reward|credit|returns?|exclusive|off|limited|guarantee|loyal|best|perfect)\b|[\d$%]', text, re.I):
                errors.append(key+': unsupported marketing or policy claim')
        if not any(c.lower() in draft.get('recommendation','').lower() for c in profile['top_categories']):
            errors.append('Recommendation must name an observed category')
        return errors

    def generate(self, profile, question, strategy='hybrid', include_profile_context=True):
        """Generate structured copy; render monetary/tier claims from retrieved policy."""
        self.validate_profile(profile)
        retrieved = self.retrieve(profile, strategy)
        profile_text = self.profile_context(profile)
        contexts = [c['text'] for c in retrieved] + ([profile_text] if include_profile_context else [])
        result = {'contexts': contexts, 'chunk_ids': [c['id'] for c in retrieved],
                  'profile_context': profile_text, 'customer_profile': profile, 'strategy': strategy}
        if re.search(r'ignore.{0,25}(system|instructions|prompt)|reveal.{0,30}(prompt|instruction)|90%|final.sale|expired.{0,30}offer|reinstate', question, re.I):
            return result | {'answer': 'I can only help with policy-grounded retention offers. Please contact support for other requests.',
                             'boundary_refusal': True, 'draft_attempts': [], 'usage': {}}
        system = (ROOT/'prompt_templates/final_offer_system.md').read_text(encoding='utf-8-sig')
        user = profile_text+'\nPOLICY EVIDENCE:\n'+'\n'.join(contexts)+'\nREQUEST: '+question
        spec = {'toolSpec': {'name': 'draft_offer', 'description': 'Draft two neutral customer-facing sentences.',
            'inputSchema': {'json': {'type': 'object', 'properties': {
                'recommendation': {'type': 'string', 'description': 'One sentence inviting exploration of an observed category.'},
                'call_to_action': {'type': 'string', 'description': 'One sentence inviting browsing and checking the account.'}},
                'required': ['recommendation','call_to_action'], 'additionalProperties': False}}}}
        attempts = []
        for attempt in range(2):
            start = time.monotonic()
            response = self.client.converse(modelId=self.model, system=[{'text': system}],
                messages=[{'role': 'user', 'content': [{'text': user}]}],
                toolConfig={'tools': [spec], 'toolChoice': {'tool': {'name': 'draft_offer'}}},
                inferenceConfig={'temperature': 0, 'maxTokens': 300})
            usage = response.get('usage', {})
            self._log({'operation': 'generation-structured', 'model': self.model, 'strategy': strategy,
                'customer_id': profile.get('customer_id'), 'input_tokens': usage.get('inputTokens',0),
                'output_tokens': usage.get('outputTokens',0), 'latency_ms': round((time.monotonic()-start)*1000),
                'request_id': response['ResponseMetadata']['RequestId']})
            blocks = response['output']['message']['content']
            draft = next((b['toolUse']['input'] for b in blocks if 'toolUse' in b), {})
            errors = self.validate_copy(draft, profile)
            attempts.append({'draft': draft, 'errors': errors, 'request_id': response['ResponseMetadata']['RequestId']})
            if not errors:
                break
            user += '\nPrevious draft rejected: '+json.dumps(errors)+'. Use only a neutral category invitation and an account-check invitation.'
        if errors:
            draft = {'recommendation': f'Explore our {profile["top_categories"][0]} category.',
                     'call_to_action': 'Browse the selection and check your account before purchasing.'}
        incentive = self.approved_incentive(profile, retrieved)
        answer = draft['recommendation'].strip()+' '+incentive+' '+draft['call_to_action'].strip()
        return result | {'answer': answer, 'draft_attempts': attempts, 'safe_fallback': bool(errors),
                         'usage': usage, 'request_id': response['ResponseMetadata']['RequestId'],
                         'policy_renderer': 'retrieved-points-row-or-conditional-gear-credit'}
