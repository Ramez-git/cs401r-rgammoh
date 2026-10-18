"""Meter only real Bedrock judge requests; preserve response bodies for RAGAS."""
import io
import json
import threading
import time
from datetime import datetime, timezone
from botocore.client import BaseClient
from botocore.response import StreamingBody

class BedrockMeter:
    def __init__(self, path, label):
        self.path, self.label = path, label
        self.lock = threading.Lock()

    def __enter__(self):
        original = BaseClient._make_api_call
        meter = self
        self.original = original
        def wrapped(client, operation, parameters):
            start = time.monotonic()
            response = original(client, operation, parameters)
            if client.meta.service_model.service_name != 'bedrock-runtime':
                return response
            if operation == 'InvokeModel':
                payload = response['body'].read()
                response['body'] = StreamingBody(io.BytesIO(payload), len(payload))
                body = json.loads(payload)
                usage = body.get('usage', {})
                incoming = usage.get('input_tokens', body.get('inputTextTokenCount', 0))
                outgoing = usage.get('output_tokens', 0)
            elif operation == 'Converse':
                usage = response.get('usage', {})
                incoming, outgoing = usage.get('inputTokens', 0), usage.get('outputTokens', 0)
            else:
                return response
            row = {'timestamp': datetime.now(timezone.utc).isoformat(), 'run': meter.label,
                   'operation': operation, 'model': parameters.get('modelId'),
                   'input_tokens': incoming, 'output_tokens': outgoing,
                   'latency_ms': round((time.monotonic()-start)*1000),
                   'request_id': response['ResponseMetadata']['RequestId']}
            with meter.lock, meter.path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row)+'\n')
            return response
        BaseClient._make_api_call = wrapped
        return self

    def __exit__(self, *args):
        BaseClient._make_api_call = self.original
