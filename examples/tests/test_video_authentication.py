import importlib.util
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('api_example', Path(__file__).resolve().parents[1] / 'video_authentication.py')
api_example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_example)
JOB = 'a' * 32


class Response:
    def __init__(self, body=None, status=200, chunks=None):
        self.body, self.status_code, self.chunks = body, status, chunks
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def close(self): pass
    def json(self): return self.body
    def raise_for_status(self):
        if self.status_code >= 400: raise api_example.requests.HTTPError(f'HTTP {self.status_code}')
    def iter_content(self, size):
        for chunk in self.chunks or []:
            if isinstance(chunk, Exception): raise chunk
            yield chunk


class Session:
    def __init__(self, responses):
        self.headers, self.calls, self.responses = {}, [], iter(responses)
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'input.mp4'
        self.source.write_bytes(b'input')
        self.output = self.root / 'signed.mp4'

    def client(self, responses):
        session = Session(responses)
        return api_example.TectraAPI('test-key', session=session), session

    def test_waits_for_done_then_downloads_and_preserves_failed_robustness(self):
        final = {'status':'done','video':{'quality_pass':True,'robustness_pass':False}}
        api, session = self.client([Response({'job_id':JOB}), Response({'status':'marking'}), Response(final), Response(chunks=[b'marked'])])
        with patch.object(api_example.time, 'sleep'):
            result = api.mark(self.source, self.output, profile='maximum-quality')
        self.assertEqual(self.output.read_bytes(), b'marked')
        self.assertFalse(result['video']['robustness_pass'])
        self.assertEqual([m for m, _, _ in session.calls], ['POST','GET','GET','GET'])
        self.assertTrue(Path(str(self.output)+'.job.json').exists())
        self.assertEqual(session.calls[0][2]['data']['profile'], 'fidelity')
        self.assertTrue(all(not c[2]['allow_redirects'] for c in session.calls))

    def test_refused_job_is_saved_and_never_downloaded(self):
        api, session = self.client([Response({'job_id':JOB}), Response({'status':'error','error':'quality floor not met'})])
        with self.assertRaises(RuntimeError): api.mark(self.source, self.output)
        self.assertEqual(len(session.calls), 2)
        self.assertFalse(self.output.exists())
        self.assertTrue(Path(str(self.output)+'.job.json').exists())

    def test_maximum_quality_requires_explicit_quality_pass(self):
        api, session = self.client([Response({'job_id':JOB}), Response({'status':'done','video':{}})])
        with self.assertRaises(RuntimeError): api.mark(self.source, self.output, profile='maximum-quality')
        self.assertEqual(len(session.calls), 2)
        self.assertFalse(self.output.exists())

    def test_failed_download_removes_partial_file(self):
        api, _ = self.client([Response({'job_id':JOB}), Response({'status':'done'}), Response(chunks=[b'partial', OSError('connection lost')])])
        with self.assertRaises(OSError): api.mark(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_stops_before_creating_a_job(self):
        self.output.write_bytes(b'keep')
        api, session = self.client([])
        with self.assertRaises(FileExistsError): api.mark(self.source, self.output)
        self.assertFalse(session.calls)
        self.assertEqual(self.output.read_bytes(), b'keep')

    def test_no_mark_and_missing_receipt_remain_explicit(self):
        api, _ = self.client([Response({'found':False})])
        output=self.root/'check.json'
        self.assertFalse(api.check(self.source, output)['found'])
        self.assertFalse(output.with_suffix('.receipt.json').exists())

    def test_received_receipt_saved_without_claiming_it_is_verified(self):
        receipt={'statement':{'proof':{'log_version':1}}}
        api, _ = self.client([Response({'found':True,'receipt':receipt})])
        output=self.root/'check.json'
        api.check(self.source, output)
        self.assertTrue(output.with_suffix('.receipt.json').exists())

    def test_cli_handles_a_pending_registration_proof(self):
        api, _ = self.client([Response({'found':True,'receipt':{'statement':{'proof':None}}})])
        output=self.root/'pending-check.json'
        text=io.StringIO()
        with patch.object(api_example, 'TectraAPI', return_value=api), \
             patch.object(api_example.sys, 'argv', ['example', 'check', str(self.source), '--out', str(output)]), \
             contextlib.redirect_stdout(text):
            code=api_example.main()
        self.assertEqual(code,0)
        self.assertIn('Registration proof is pending',text.getvalue())
        self.assertNotIn('exact original verified',text.getvalue())

    def test_redirect_is_rejected_without_a_second_request(self):
        api, session = self.client([Response(status=302)])
        with self.assertRaises(RuntimeError): api.mark(self.source, self.output)
        self.assertEqual(len(session.calls),1)

    def test_timeout_does_not_resubmit_marking(self):
        api, session = self.client([Response({'job_id':JOB}), Response({'status':'queued'})])
        with self.assertRaises(TimeoutError): api.mark(self.source, self.output, wait_seconds=-1)
        self.assertEqual([m for m, _, _ in session.calls], ['POST','GET'])


if __name__ == '__main__': unittest.main()
