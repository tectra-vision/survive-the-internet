import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from nacl.signing import SigningKey

spec=importlib.util.spec_from_file_location('verifier', Path(__file__).resolve().parents[1]/'verify_receipt.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class ExactFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.file=self.root/'original.mp4'
        self.file.write_bytes(b'original-video-bytes')
        self.key=SigningKey.generate()
        self.public=self.key.verify_key.encode().hex()

    def receipt(self, version):
        commit=b'c'*32
        mid, issued=1234, 1700000000
        proof={'mark_id':f'{mid:012x}', 'issued_at':issued,'commitment':commit.hex(),'log_version':version}
        if version==2:
            manifest='{"version":1}'
            digest=hashlib.sha256(self.file.read_bytes()).digest()
            manifest_hash=hashlib.sha256(manifest.encode()).digest()
            record=v.sha(b'tectra-content-v1',digest,struct.pack('>Q',self.file.stat().st_size),manifest_hash)
            proof['content']={'delivered_sha256':digest.hex(),'delivered_size':self.file.stat().st_size,'reference_manifest':manifest,'reference_manifest_sha256':manifest_hash.hex(),'record':record.hex()}
            leaf=v.sha(b'\x00',b'tectra-log-v2',mid.to_bytes(6,'big'),struct.pack('>Q',issued),commit,record)
        else:
            leaf=v.sha(b'\x00',b'tectra-log-v1',mid.to_bytes(6,'big'),struct.pack('>Q',issued),commit)
        proof['leaf']=leaf.hex()
        prev=b'p'*32
        proof['batch']={'id':1,'index':0,'leaf_count':1,'path':[],'root':leaf.hex(),'prev_chain':prev.hex(),'total_size':1,'chain':v.sha(b'tectra-chain-v1',prev,leaf,struct.pack('>Q',1)).hex()}
        statement={'proof':proof,'file_sha256':hashlib.sha256(self.file.read_bytes()).hexdigest(),'result':{'registry_size_used':1,'threshold':v.threshold(1),'score':0.99,'method':'correlation'},'log':{'committed_size':1}}
        return {'statement':statement,'public_key':self.public,'signature':base64.b64encode(self.key.sign(json.dumps(statement,sort_keys=True,separators=(',',':')).encode()).signature).decode()}

    def run_verifier(self, receipt, original=True):
        path=self.root/'receipt.json'
        path.write_text(json.dumps(receipt))
        args=['verify_receipt.py',str(path),'--key',self.public]
        if original:args+=['--original',str(self.file)]
        output=io.StringIO()
        with patch.object(v.sys,'argv',args), patch.object(v.urllib.request,'urlopen',side_effect=OSError('offline test')), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as exit: v.main()
        return exit.exception.code,output.getvalue()

    def test_exact_original_passes_with_content_bound_receipt(self):
        code,output=self.run_verifier(self.receipt(2))
        self.assertEqual(code,0)
        self.assertIn('PASS  4b original file',output)

    def test_changed_original_fails_even_with_valid_receipt_signature(self):
        receipt=self.receipt(2)
        self.file.write_bytes(b'changed-video-bytes')
        code,output=self.run_verifier(receipt)
        self.assertEqual(code,1)
        self.assertIn('PASS  1 signature',output)
        self.assertIn('FAIL  4b original file',output)

    def test_legacy_receipt_cannot_silently_skip_requested_original_check(self):
        code,output=self.run_verifier(self.receipt(1))
        self.assertEqual(code,1)
        self.assertIn('no registered-file commitment',output)

    def test_legacy_receipt_can_still_authenticate_its_registration(self):
        code,_=self.run_verifier(self.receipt(1),original=False)
        self.assertEqual(code,0)

    def test_pending_proof_is_reported_as_unavailable(self):
        receipt=self.receipt(2)
        receipt['statement']['proof']=None
        receipt['signature']=base64.b64encode(self.key.sign(json.dumps(receipt['statement'],sort_keys=True,separators=(',',':')).encode()).signature).decode()
        code,output=self.run_verifier(receipt)
        self.assertEqual(code,1)
        self.assertIn('PASS  1 signature',output)
        self.assertIn('registration proof',output)
        self.assertIn('not available yet',output)

    def test_altered_commitment_fails_signature_validation(self):
        receipt=copy.deepcopy(self.receipt(2))
        receipt['statement']['proof']['content']['delivered_sha256']='0'*64
        code,output=self.run_verifier(receipt)
        self.assertEqual(code,1)
        self.assertIn('FAIL  1 signature',output)


if __name__=='__main__': unittest.main()
