"""Re-run the two required pre-lab checks without creating persistent resources."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import boto3
from botocore.config import Config
root=Path(__file__).resolve().parents[1]
client=boto3.client('bedrock-runtime',region_name='us-east-1',config=Config(retries={'max_attempts':1}))
lines=['Bedrock access verification',datetime.now(ZoneInfo('America/Denver')).isoformat(),'Region: us-east-1','']
ok=True
try:
    r=client.invoke_model(modelId='amazon.titan-embed-text-v2:0',body=json.dumps({'inputText':'30 day return policy'}))
    dim=len(json.loads(r['body'].read())['embedding'])
    lines.append(f'PASS  Titan embeddings        dim={dim}')
except Exception as e:
    ok=False;lines.append(f'FAIL  Titan embeddings        {type(e).__name__}: {str(e)[:200]}')
try:
    r=client.converse(modelId='us.anthropic.claude-haiku-4-5-20251001-v1:0',messages=[{'role':'user','content':[{'text':'Reply with OK'}]}],inferenceConfig={'maxTokens':10})
    text=r['output']['message']['content'][0]['text'].strip()
    lines.append(f'PASS  Claude Haiku 4.5        {text!r}')
except Exception as e:
    ok=False;lines.append(f'FAIL  Claude Haiku 4.5        {type(e).__name__}: {str(e)[:200]}')
text='\n'.join(lines)+'\n'
(root/'docs/bedrock-access-verification.txt').write_text(text,encoding='utf-8')
print(text)
raise SystemExit(0 if ok else 1)
