"""Generated HTTP/FD controls only. Real sockets and DNS are forbidden."""
from pathlib import Path
import hashlib, http.client, importlib.util, io, json, os, socket, ssl, stat, struct, tempfile, time, unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
CLIENT = HERE / 'client.py'
spec = importlib.util.spec_from_file_location("generated_owned_https_client", CLIENT)
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
SOURCE_ROOT = Path(os.environ.get('NEURAL077_TEST_IMPLEMENTATIONS_ROOT', str(Path(__file__).resolve().parents[2])))
BRIDGE = SOURCE_ROOT / 'waveform-transport-v1/provider_bridge.py'
TRIAL = 'development-001-' + 'a' * 24
PROMPT = 'Do not use tools, code execution, external retrieval, files, or memory from other query trials.\n' + TRIAL + '\nGenerated samples: [0.1,0.2].'
MODEL = 'generated-resolved-model-01'
TOKEN = b'sk-GENERATED-NOT-A-CREDENTIAL-012345'
PREFIX = struct.Struct('!I')
WRITTEN = 0


def config(prompt=PROMPT):
    return {'schema':'neural077_openai_client_v1','model':MODEL,'max_output_tokens':64,
            'deadline':time.monotonic()+30,'trial_id':TRIAL,'context_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
            'bridge_path':str(BRIDGE),'bridge_pin':dict(c.BRIDGE_PIN)}


def response_for(request):
    value=json.loads(request)
    answer={'trial_id':TRIAL,'target_probability':0.5}
    return {'object':'response','status':'completed','error':None,'incomplete_details':None,
        'tools':[],'tool_choice':'none','parallel_tool_calls':False,'store':False,'truncation':'disabled',
        'previous_response_id':None,'conversation':None,'model':value['model'],'max_output_tokens':value['max_output_tokens'],
        'id':'resp_generated01','output':[{'type':'message','role':'assistant','status':'completed',
            'content':[{'type':'output_text','text':json.dumps(answer)}]}],
        'usage':{'input_tokens':10,'output_tokens':2,'total_tokens':12}}


class Reply:
    def __init__(self, raw, *, status=200, chunk=11, error=None, fail_after=0, missing=0, close_error=False, encoding='identity'):
        self.raw=raw;self.at=0;self.status=status;self.chunk=chunk;self.error=error;self.fail_after=fail_after
        self.length=len(raw)+missing;self.closed=False;self.close_error=close_error;self.encoding=encoding
        self.requests=[]
    def read(self, size):
        self.requests.append(size)
        if self.error is not None and self.at>=self.fail_after:
            error,self.error=self.error,None
            raise error
        part=self.raw[self.at:self.at+min(size,self.chunk)];self.at+=len(part);self.length-=len(part)
        return part
    def getheader(self, name, default=None):
        assert name=='Content-Encoding';return self.encoding
    def close(self):
        self.closed=True
        if self.close_error:raise OSError('generated close failure '+TOKEN.decode())


class Connection:
    def __init__(self, owner):
        self.owner=owner;self.sock=Mock();self.closed=False;self.sent=[];self.debug=[];self.reply=None
    def set_debuglevel(self, value):self.debug.append(value)
    def request(self, method, target, **kwargs):
        self.sent.append((method,target,kwargs))
        if self.owner.request_error:raise self.owner.request_error
    def getresponse(self):
        raw=self.sent[0][2]['body'];value=response_for(raw)
        if self.owner.mutate:self.owner.mutate(value)
        self.reply=self.owner.reply or Reply(json.dumps(value).encode())
        return self.reply
    def close(self):
        self.closed=True;self.sock=None
        if self.owner.close_error:raise OSError('generated connection close failure')


class Factory:
    def __init__(self, *, reply=None, request_error=None, mutate=None, close_error=False):
        self.reply=reply;self.request_error=request_error;self.mutate=mutate;self.close_error=close_error
        self.calls=[];self.connection=None
    def __call__(self, host, *, port, timeout, context):
        self.calls.append((host,port,timeout,context.check_hostname,context.verify_mode))
        self.connection=Connection(self);return self.connection


class ClientControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='generated-provider-client-')
        self.root=Path(self.tmp.name).resolve();self.directory=self.root/'custody';self.directory.mkdir(mode=0o700)
        self.stack=[]
        for name in ('create_connection','getaddrinfo'):
            guard=patch.object(socket,name,side_effect=AssertionError('network forbidden in generated controls'))
            guard.start();self.addCleanup(guard.stop)
    def tearDown(self):
        global WRITTEN
        WRITTEN+=sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file() and not p.is_symlink())
        for fd in self.stack:
            try:os.close(fd)
            except OSError:pass
        self.tmp.cleanup()
    def read(self, name):return json.loads((self.directory/name).read_bytes())
    def run_client(self, factory=None, *, selected=None, token=TOKEN, raw_input=None):
        factory=factory or Factory();selected=selected or config()
        secret_r,secret_w=os.pipe();config_r,config_w=os.pipe();directory=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY)
        self.stack.extend((secret_r,config_r,directory))
        os.write(config_w,c.encode(selected));os.close(config_w)
        os.write(secret_w,token);os.close(secret_w)
        body=PROMPT.encode();input_stream=io.BytesIO(PREFIX.pack(len(body))+body if raw_input is None else raw_input)
        output=io.BytesIO()
        code=c.main(['--credential-fd',str(secret_r),'--config-fd',str(config_r),'--custody-fd',str(directory)],
                    http_factory=factory,input_stream=input_stream,output_stream=output)
        for fd in (secret_r,config_r,directory):
            with self.assertRaises(OSError):os.fstat(fd)
        return code,output.getvalue(),factory
    def direct(self, factory, cap=64, selected=None):
        selected=selected or config();fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY);self.stack.append(fd)
        bridge=c.load_bridge(selected);custody=c.Custody(fd,c.pin(c.encode(selected)),selected['deadline'])
        sender=c.Sender(selected,custody.config_pin,TOKEN.decode(),custody,bridge,Mock(),factory,response_cap=cap)
        return sender,bridge.request_body(PROMPT,MODEL,64)
    def no_secret(self):
        for path in self.directory.iterdir():
            raw=path.read_bytes();self.assertNotIn(TOKEN,raw);self.assertNotIn(b'Authorization',raw)

    def test_01_full_wrapper_original_bridge_exact_frames_and_private_custody(self):
        code,output,factory=self.run_client()
        self.assertEqual(code,0);self.assertEqual(set(p.name for p in self.directory.iterdir()),c.FILES)
        size=PREFIX.unpack(output[:4])[0];self.assertEqual(size,len(output)-4)
        self.assertEqual(json.loads(output[4:]),{'trial_id':TRIAL,'target_probability':0.5})
        request=(self.directory/'REQUEST.bin').read_bytes();response=(self.directory/'RESPONSE.bin').read_bytes()
        http=self.read('HTTP.json');bridge=self.read('BRIDGE.json')
        self.assertEqual(http['request'],c.pin(request));self.assertEqual(http['response'],c.pin(response))
        self.assertTrue(http['request_complete'] and http['response_complete'] and http['connection_closed'])
        self.assertIsNone(http['failure']);self.assertEqual(http['status_code'],200)
        self.assertEqual(http['requests_attempted'],1);self.assertFalse(http['body_overflow'])
        self.assertEqual(bridge['receipt']['request'],c.pin(request));self.assertEqual(bridge['receipt']['response'],c.pin(response))
        self.assertEqual(bridge['receipt']['answer'],c.pin(output[4:]));self.assertEqual(bridge['status'],'recorded')
        self.assertEqual(len(factory.calls),1);self.assertEqual(factory.calls[0][:2],('api.openai.com',443))
        self.assertEqual(factory.calls[0][3:],(True,ssl.CERT_REQUIRED))
        method,target,kwargs=factory.connection.sent[0]
        self.assertEqual((method,target),('POST','/v1/responses'));self.assertFalse(kwargs['encode_chunked'])
        self.assertEqual(kwargs['headers']['Authorization'],'Bearer '+TOKEN.decode())
        self.assertEqual(factory.connection.debug,[0]);self.assertTrue(factory.connection.closed and factory.connection.reply.closed)
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode)==0o600 for p in self.directory.iterdir()))
        self.no_secret()

    def test_02_second_prompt_refused_before_http(self):
        raw=PROMPT.encode();code,output,factory=self.run_client(raw_input=PREFIX.pack(len(raw))+raw+b'\0')
        self.assertEqual((code,output),(3,b''));self.assertEqual(factory.calls,[])
        self.assertEqual(self.read('BRIDGE.json')['status'],'not_called');self.assertEqual(self.read('HTTP.json')['requests_attempted'],0)

    def test_03_model_mismatch_retains_exact_raw_response_without_answer(self):
        factory=Factory(mutate=lambda value:value.update(model='wrong-model'))
        code,output,factory=self.run_client(factory)
        self.assertEqual((code,output),(3,b''));self.assertEqual(len(factory.calls),1)
        self.assertTrue(self.read('HTTP.json')['response_complete'])
        self.assertEqual(self.read('BRIDGE.json')['receipt']['status'],'failed_no_answer')
        self.assertEqual(json.loads((self.directory/'RESPONSE.bin').read_bytes())['model'],'wrong-model')

    def test_04_redirect_body_retained_no_follow_or_retry(self):
        raw=b'{"generated":"redirect"}';factory=Factory(reply=Reply(raw,status=302))
        code,output,_=self.run_client(factory);self.assertEqual((code,output),(3,b''))
        self.assertEqual((self.directory/'RESPONSE.bin').read_bytes(),raw)
        receipt=self.read('HTTP.json');self.assertEqual(receipt['status_code'],302)
        self.assertEqual((receipt['requests_attempted'],receipt['redirects_followed'],receipt['retries']),(1,0,0))
        self.assertEqual(receipt['failure'],'http_status');self.assertTrue(receipt['connection_closed'])

    def test_05_network_error_diagnostics_cannot_leak_credential(self):
        factory=Factory(request_error=OSError('Authorization: Bearer '+TOKEN.decode()))
        code,output,_=self.run_client(factory);self.assertEqual((code,output),(3,b''))
        self.assertEqual(self.read('HTTP.json')['failure'],'network_error');self.no_secret()

    def test_06_oversize_retains_exact_cap_plus_one_prefix_and_closes(self):
        factory=Factory(reply=Reply(b'x'*200,chunk=7));sender,request=self.direct(factory,cap=64)
        with self.assertRaisesRegex(c.Refused,'response_oversize'):sender(request)
        self.assertEqual((self.directory/'RESPONSE.bin').read_bytes(),b'x'*65)
        receipt=self.read('HTTP.json');self.assertTrue(receipt['body_overflow']);self.assertFalse(receipt['response_complete'])
        self.assertTrue(factory.connection.closed and factory.connection.reply.closed)
        self.assertTrue(all(0<size<=65 for size in factory.connection.reply.requests))

    def test_07_incomplete_read_retains_exception_partial_after_prior_prefix(self):
        reply=Reply(b'prefix',chunk=6,error=http.client.IncompleteRead(b'partial',10),fail_after=6)
        sender,request=self.direct(Factory(reply=reply))
        with self.assertRaisesRegex(c.Refused,'incomplete_body'):sender(request)
        self.assertEqual((self.directory/'RESPONSE.bin').read_bytes(),b'prefixpartial')
        self.assertFalse(self.read('HTTP.json')['response_complete'])

    def test_08_silent_short_content_length_refused(self):
        sender,request=self.direct(Factory(reply=Reply(b'abc',missing=10)))
        with self.assertRaisesRegex(c.Refused,'incomplete_body'):sender(request)
        self.assertEqual((self.directory/'RESPONSE.bin').read_bytes(),b'abc')

    def test_09_close_failure_preserved_even_when_http_failure_already_exists(self):
        sender,request=self.direct(Factory(reply=Reply(b'{}',status=400,close_error=True)))
        with self.assertRaisesRegex(c.Refused,'http_status'):sender(request)
        self.assertFalse(self.read('HTTP.json')['connection_closed']);self.no_secret()

    def test_10_wrong_context_refused_before_http(self):
        selected=config();selected['context_sha256']='0'*64
        code,output,factory=self.run_client(selected=selected)
        self.assertEqual((code,output),(3,b''));self.assertEqual(factory.calls,[])
        self.assertEqual(self.read('HTTP.json')['failure'],'context_mismatch')

    def test_11_credential_newline_refused_and_not_retained(self):
        code,output,factory=self.run_client(token=TOKEN+b'\r\n')
        self.assertEqual((code,output),(3,b''));self.assertEqual(factory.calls,[]);self.no_secret()

    def test_12_configuration_exact_fields_deadline_and_model(self):
        for key,value in [('endpoint','https://untrusted.invalid'),('deadline',time.monotonic()-1),('max_output_tokens',True),('bridge_pin',{'bytes':1,'sha256':'0'*64})]:
            selected=config();selected[key]=value
            with self.assertRaises(c.Refused):c.configuration(c.encode(selected))
        raw=c.encode(config());raw=raw[:-2]+b',"schema":"duplicate"}\n'
        with self.assertRaises(c.Refused):c.configuration(raw)

    def test_13_changed_bridge_source_refused_before_compile_or_http(self):
        changed=self.root/'provider_bridge.py';raw=BRIDGE.read_bytes();changed.write_bytes(b'x'+raw[1:])
        selected=config();selected['bridge_path']=str(changed)
        code,output,factory=self.run_client(selected=selected)
        self.assertEqual((code,output),(3,b''));self.assertEqual(factory.calls,[])

    def test_14_receipt_sink_failure_emits_no_answer(self):
        original=c.Custody.json
        def sink(owner,name,value):
            if name=='BRIDGE.json':raise c.Refused('generated_sink_failure')
            return original(owner,name,value)
        with patch.object(c.Custody,'json',sink):code,output,factory=self.run_client()
        self.assertEqual((code,output),(3,b''));self.assertEqual(len(factory.calls),1)
        self.assertTrue((self.directory/'RESPONSE.bin').is_file())

    def test_15_deadline_retains_received_prefix_and_closes(self):
        reply=Reply(b'prefix',chunk=6,error=c.Deadline('deadline'),fail_after=6)
        sender,request=self.direct(Factory(reply=reply))
        with self.assertRaisesRegex(c.Refused,'deadline'):sender(request)
        self.assertEqual((self.directory/'RESPONSE.bin').read_bytes(),b'prefix')
        self.assertTrue(self.read('HTTP.json')['connection_closed'])

    def test_16_literal_credential_echo_across_chunks_retains_only_prior_prefix(self):
        raw=b'public-prefix:'+TOKEN+b':suffix'
        sender,request=self.direct(Factory(reply=Reply(raw,chunk=5)),cap=128)
        with self.assertRaisesRegex(c.Refused,'credential_echo'):sender(request)
        self.assertEqual((self.directory/'RESPONSE.bin').read_bytes(),b'public-prefix:')
        self.assertFalse(self.read('HTTP.json')['response_complete']);self.no_secret()

    def test_17_credential_in_request_refused_before_persistence_or_send(self):
        sender,request=self.direct(Factory())
        request=request.replace(b'Generated samples',TOKEN)
        with self.assertRaisesRegex(c.Refused,'credential_echo'):sender(request)
        self.assertEqual((self.directory/'REQUEST.bin').read_bytes(),b'')
        self.assertEqual(self.read('HTTP.json')['requests_attempted'],0);self.no_secret()

    def test_18_second_sender_call_refused_without_second_request(self):
        factory=Factory(reply=Reply(b'{}'));sender,request=self.direct(factory)
        self.assertEqual(sender(request),b'{}')
        with self.assertRaisesRegex(c.Refused,'second_sender_call'):sender(request)
        self.assertEqual(len(factory.connection.sent),1)

    def test_19_unexpected_custody_member_prevents_answer_before_serve_returns(self):
        original=c.Custody.json
        def sink(owner,name,value):
            result=original(owner,name,value)
            if name=='BRIDGE.json':(self.directory/'extra').write_bytes(b'x')
            return result
        with patch.object(c.Custody,'json',sink):code,output,_=self.run_client()
        self.assertEqual((code,output),(3,b''))

    def test_20_pipe_read_requires_eof_and_obeys_monotonic_deadline(self):
        r,w=os.pipe();self.stack.extend((r,w));os.write(w,b'partial')
        with self.assertRaises(c.Deadline):c.pipe_body(r,16,time.monotonic()+0.002)

    def test_21_fd_arguments_reject_collision_aliases_and_duplicate_flags(self):
        for argv in [[],['--credential-fd','3','--config-fd','3','--custody-fd','4'],
            ['--credential-fd','3','--credential-fd','4','--custody-fd','5'],
            ['--credential-fd=3','4','--config-fd','5','--custody-fd','6']]:
            with self.assertRaises(c.Refused):c.arguments(argv)

    def test_22_decoded_provider_id_cannot_reintroduce_literal_credential_into_receipt(self):
        bridge=c.load_bridge(config());request=bridge.request_body(PROMPT,MODEL,64)
        value=response_for(request);value['id']='resp_'+TOKEN.decode()
        raw=json.dumps(value).encode().replace(TOKEN,b''.join(('\\u%04x'%byte).encode() for byte in TOKEN))
        self.assertNotIn(TOKEN,raw)
        code,output,factory=self.run_client(Factory(reply=Reply(raw)))
        self.assertEqual((code,output),(3,b''));self.assertEqual(len(factory.calls),1)
        self.assertEqual((self.directory/'RESPONSE.bin').read_bytes(),raw)
        self.assertNotEqual(self.read('BRIDGE.json')['status'],'recorded');self.no_secret()


if __name__=='__main__':
    result=unittest.main(verbosity=2,exit=False)
    print(json.dumps({'generated_fixture_body_bytes':WRITTEN,'network_calls':0,'models':0,
                      'literal_credential_marker_is_generated':True},sort_keys=True))
    raise SystemExit(0 if result.result.wasSuccessful() else 1)
