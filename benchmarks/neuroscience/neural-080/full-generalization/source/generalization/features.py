"""Full fixed generalization features from authenticated local media and weights.

This is prospective source, not an assertion of native qualification, media
rights, checkpoint training exposure, clock calibration, or reference competence.
All scientific imports are lazy. No weight loader or decoder can fetch a URL.
The enclosing operator must provide process-level memory/CPU/native restrictions;
Owner accounts logical allocations and effects, not unobservable native peaks.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import io
import math
import time

from input_owner import need, capture, descriptor, Writer
from .source_map import SourceMap, MediaRole, VIDEO_IDS


VERSIONS = {"numpy": "2.2.6", "torch": "2.7.1", "torchvision": "0.22.1",
            "opencv": "4.11.0", "scipy": "1.15.3", "av": "14.4.0"}
VISION_REVISION = "59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca"
OPENCV_REVISION = "31b0eeea0b44b370fd0712312df4214d4ae1b158"
# This prefix comes from the official KINETICS400_V1 source URL. It is not a
# full checkpoint digest or an issuer; the separately admitted descriptor is.
KINETICS400_PREFIX = "d76dad2f"
NODES = ("features.1", "features.2", "features.3.1", "features.4",
         "features.5.cat", "features.6.cat", "features.7", "features.8.cat",
         "features.9.cat", "features.10.cat", "features.11.cat",
         "features.12.cat", "features.13", "features.14.cat",
         "features.15.cat", "avgpool", "classifier.1")
# Exact output geometry for batch1,14 RGB frames,224x224, the unchanged source
# convolutions/pools and eval mode. cat is the enclosing inception return value.
NODE_SHAPES = ((64,7,56,56), (64,7,56,56), (192,7,56,56), (192,7,28,28),
               (256,7,28,28), (480,7,28,28), (480,4,14,14), (512,4,14,14),
               (512,4,14,14), (512,4,14,14), (528,4,14,14), (832,4,14,14),
               (832,2,7,7), (832,2,7,7), (1024,2,7,7), (1024,1,1,1),
               (400,1,1,1))
FEATURE_DIM = sum(math.prod(s) for s in NODE_SHAPES)
BLOCK_DIMS = {"matched_static": FEATURE_DIM, "motion": 30*8*8*8,
              "acoustic": 300*64+60, "learned_video": FEATURE_DIM,
              "learned_video_reversed": FEATURE_DIM, "silence": 1}
MIDPOINTS = tuple(Fraction((2*j+1)*3,28) for j in range(14))


@dataclass(frozen=True)
class FeatureLimits:
    """No inferred allowances. Bytes count complete arrays, never truncation."""
    max_native_frame_bytes: int
    max_work_array_bytes: int
    max_feature_vector_bytes: int
    max_checkpoint_bytes: int
    max_checkpoint_tensor_bytes: int
    max_model_tensor_bytes: int

    def validate(self):
        need(all(type(v) is int and 0 < v < 2**63 for v in vars(self).values()),
             "explicit positive full feature/native allocation capacities")
        need(self.max_feature_vector_bytes >= FEATURE_DIM*8,
             "all17node full float64 matched-static accumulator required")
        return self


def reserve(owner, limits, amount, label, *, vector=False):
    need(type(amount) is int and amount >= 0, "integer allocation extent")
    cap = limits.max_feature_vector_bytes if vector else limits.max_work_array_bytes
    need(amount <= cap, "complete feature allocation exceeds selected capacity: "+label)
    owner.reserve("retained_bytes", amount)


def fraction_pair(x):
    return [x.numerator, x.denominator]


def modules():
    import numpy as np
    import torch
    import torchvision
    import cv2
    import scipy
    import av
    actual = {"numpy": np.__version__, "torch": torch.__version__.split("+")[0],
              "torchvision": torchvision.__version__.split("+")[0],
              "opencv": cv2.__version__, "scipy": scipy.__version__, "av": av.__version__}
    need(actual == VERSIONS, "exact selected full feature runtime versions")
    return np, torch, torchvision, cv2, scipy, av


class Encoder:
    """Exact local S3D; capture module outputs equivalent to all17 FX nodes."""
    def __init__(self, root, checkpoint, owner, limits, runtime):
        rec = owner.begin("generalization_local_s3d_checkpoint")
        buffer = None
        try:
            self.owner, self.limits = owner, limits.validate()
            self.np, self.torch, self.vision = runtime[:3]
            need(self.torch.get_default_device() == self.torch.device("cpu") and
                 self.torch.get_default_dtype() == self.torch.float32,
                 "explicit CPU float32 architecture construction environment")
            descriptor(checkpoint, max_bytes=limits.max_checkpoint_bytes)
            need(checkpoint["sha256"].startswith(KINETICS400_PREFIX),
                 "admitted full checkpoint SHA256 must match official KINETICS400 prefix")
            raw = capture(root, checkpoint, owner, max_bytes=limits.max_checkpoint_bytes)
            reserve(owner, limits, len(raw), "checkpoint BytesIO")
            buffer = io.BytesIO(raw)
            owner.reserve("retained_bytes", limits.max_checkpoint_tensor_bytes)
            owner.reserve("retained_bytes", limits.max_model_tensor_bytes)
            # weights=None prevents torchvision's download route. Explicit true
            # prevents the default/environment from choosing general unpickling.
            state = self.torch.load(buffer, weights_only=True, map_location="cpu")
            need(isinstance(state, dict) and state and all(type(k) is str and
                 isinstance(v, self.torch.Tensor) and v.device.type == "cpu" and
                 v.layout == self.torch.strided for k,v in state.items()),
                 "ordinary CPU tensor state_dict only")
            state_bytes = sum(v.numel()*v.element_size() for v in state.values())
            need(state_bytes <= limits.max_checkpoint_tensor_bytes,
                 "checkpoint expanded tensor capacity; external sandbox bounds deserialization peak")
            self.model = self.vision.models.video.s3d(weights=None)
            model_bytes = sum(v.numel()*v.element_size() for v in self.model.state_dict().values())
            need(model_bytes <= limits.max_model_tensor_bytes, "complete S3D model capacity")
            self.model.load_state_dict(state, strict=True)
            self.model.eval()
            need(all(v.device.type == "cpu" and (not v.is_floating_point() or v.dtype == self.torch.float32)
                     for v in self.model.state_dict().values()), "CPU float32 encoder")
            self.transform = self.vision.models.video.S3D_Weights.KINETICS400_V1.transforms()
            self.checkpoint = dict(checkpoint)
            self.calls = 0
        except BaseException as exc:
            owner.failure(rec, exc)
        finally:
            if buffer is not None:
                owner.close(rec, buffer.close)
        owner.complete(rec)

    def vector(self, frames):
        rec = self.owner.begin("s3d_all17_forward")
        result = None
        try:
            np, torch = self.np, self.torch
            need(len(frames) == 14 and all(f.dtype == np.uint8 and f.ndim == 3 and
                 f.shape == frames[0].shape and f.shape[-1] == 3 for f in frames),
                 "14 authentic RGB frames on identical native geometry")
            raw_bytes = sum(int(f.nbytes) for f in frames)
            reserve(self.owner, self.limits, raw_bytes, "stacked14 RGB frames")
            reserve(self.owner, self.limits, 14*3*256*256*4*3, "published transform tensors")
            reserve(self.owner, self.limits, FEATURE_DIM*4, "all17 output vector", vector=True)
            # A conservative logical intermediate allowance; native peak remains
            # an independently measured deployment gate, never this estimate.
            reserve(self.owner, self.limits, FEATURE_DIM*4*4, "S3D activation workspace")
            clip = torch.from_numpy(np.stack(frames)).permute(0,3,1,2).contiguous()
            with torch.inference_mode():
                x = self.transform(clip).unsqueeze(0)
                need(tuple(x.shape) == (1,3,14,224,224), "published S3D transform geometry")
                result = np.empty(FEATURE_DIM, dtype=np.float32)
                cursor = 0
                def retain(node, value):
                    nonlocal cursor
                    index = NODES.index(node)
                    need(tuple(value.shape) == (1,*NODE_SHAPES[index]), "full official node geometry: "+node)
                    flat = value.reshape(-1)
                    need(bool(torch.isfinite(flat).all()), "finite full S3D activation")
                    n = flat.numel()
                    result[cursor:cursor+n] = flat.cpu().numpy()
                    cursor += n
                # The named cat operations are literally returned by the
                # enclosing SepInceptionBlock3D; features.3.1 is its temporal
                # submodule and the final return of features.3. No layer omitted.
                x = self.model.features[0](x)
                for i in range(1,16):
                    x = self.model.features[i](x)
                    name = "features.3.1" if i == 3 else ("features.%d.cat" % i
                           if i in (5,6,8,9,10,11,12,14,15) else "features.%d" % i)
                    retain(name,x)
                x = self.model.avgpool(x); retain("avgpool",x)
                x = self.model.classifier(x); retain("classifier.1",x)
                need(cursor == FEATURE_DIM, "complete chronological all17 concatenation")
            self.calls += 1
        except BaseException as exc:
            self.owner.failure(rec, exc)
        self.owner.complete(rec)
        return result


def flow_histogram(previous, current, delta, np, cv2, owner, limits):
    need(previous.shape == current.shape and previous.dtype == current.dtype == np.uint8,
         "native adjacent grayscale geometry is fixed")
    need(delta > 0, "positive actual PTS displacement interval")
    h,w = current.shape
    reserve(owner, limits, h*w*128, "full dense flow and histogram workspace")
    flow = cv2.calcOpticalFlowFarneback(previous,current,None,0.5,3,15,3,5,1.2,0)
    need(flow.shape == (h,w,2) and flow.dtype == np.float32 and np.isfinite(flow).all(),
         "complete finite native Farneback displacement")
    velocity = flow.astype(np.float64)/float(delta)
    magnitude = np.hypot(velocity[...,0],velocity[...,1])
    direction = np.floor(np.mod(np.arctan2(velocity[...,1],velocity[...,0]),2*np.pi)*(8/(2*np.pi))).astype(np.int64)
    direction = np.minimum(direction,7)
    ys,xs = np.arange(9)*h//8,np.arange(9)*w//8
    out = np.empty((8,8,8),dtype=np.float64)
    for y in range(8):
        for x in range(8):
            m=magnitude[ys[y]:ys[y+1],xs[x]:xs[x+1]]
            d=direction[ys[y]:ys[y+1],xs[x]:xs[x+1]]
            # Sum directional magnitude / all cell pixels, including zeros.
            out[y,x]=np.bincount(d.ravel(),weights=m.ravel(),minlength=8)/m.size
    return out


def motion_bins(histograms, midpoints, np, owner, limits):
    need(histograms and len(histograms) == len(midpoints) and
         all(b>a for a,b in zip(midpoints,midpoints[1:])), "all adjacent transition clocks")
    boundaries = [None]+[(a+b)/2 for a,b in zip(midpoints,midpoints[1:])]+[None]
    reserve(owner,limits,30*8*8*8*8,"full30 dense-motion bins")
    out=np.zeros((30,8,8,8),dtype=np.float64)
    support=[Fraction(0) for _ in range(30)]
    for i,hist in enumerate(histograms):
        a=Fraction(0) if boundaries[i] is None else max(Fraction(0),boundaries[i])
        b=Fraction(3) if boundaries[i+1] is None else min(Fraction(3),boundaries[i+1])
        if b<=a:continue
        for j in range(30):
            duration=max(Fraction(0),min(b,Fraction(j+1,10))-max(a,Fraction(j,10)))
            if duration:
                out[j]+=hist*float(duration*10);support[j]+=duration
    need(all(s==Fraction(1,10) for s in support) and np.isfinite(out).all(),
         "every motion bin has full duration support with declared nearest-transition boundary convention")
    return out.reshape(-1)


def decode_features(root, role, versions, owner, limits, runtime):
    """Full captured-media demux; no nominal FPS, padding repair or absent-audio imputation."""
    rec=owner.begin("full_native_feature_decode:%04d"%role.video_id)
    np,torch,vision,cv2,scipy,av=runtime
    buffer=container=None;answer=None
    try:
        from decode_media import frame_interval, audio_interval, normalized_audio
        need(isinstance(role,MediaRole),"validated actual media role")
        need({k:tuple(v) for k,v in av.library_versions.items()}==dict(versions),"exact selected native library versions")
        raw=capture(root,role.source_media,owner)
        reserve(owner,limits,len(raw),"captured media BytesIO")
        buffer=io.BytesIO(raw)
        container=av.open(buffer,mode="r",format=role.container,options={"protocol_whitelist":"pipe"})
        streams={s.index:s for s in container.streams}
        need(role.video_stream in streams and streams[role.video_stream].type=="video","selected actual video stream")
        video=streams[role.video_stream];selected=[video];video.codec_context.thread_count=1
        if role.audio_status=="presented_silent_no_track":
            need(role.audio_stream is None and not any(s.type=="audio" for s in streams.values()),"verified no-track silence must actually have no audio track")
        else:
            need(role.audio_status=="presented_audio" and role.audio_stream in streams and
                 streams[role.audio_stream].type=="audio","known heard-audio track required")
            selected.append(streams[role.audio_stream]);selected[-1].codec_context.thread_count=1
        origin=Fraction(*role.timeline_origin);frames=[None]*14;frame_indices=[None]*14
        starts=[];ends=[];hist=[];midpoints=[];previous=None;geometry=None
        audio=[];audio_start=audio_end=None;rate=None;layout=None;sample_count=0
        for packet in container.demux(*selected):
            for frame in packet.decode():
                if packet.stream.index==role.video_stream:
                    need(len(starts)<role.max_frames and 8<=frame.width<=role.max_width and
                         8<=frame.height<=role.max_height,"full native frame extent before array conversion")
                    size=frame.width*frame.height*3
                    need(size<=limits.max_native_frame_bytes,"native RGB frame capacity")
                    reserve(owner,limits,size+frame.width*frame.height,"native RGB and grayscale frame")
                    a,b=frame_interval(frame,origin)
                    need(not ends or a==ends[-1],"actual contiguous frame PTS intervals")
                    need(geometry is None or geometry==(frame.height,frame.width),"unchanged native frame geometry")
                    geometry=(frame.height,frame.width)
                    rgb=frame.to_ndarray(format="rgb24")
                    need(rgb.shape==(*geometry,3) and rgb.dtype==np.uint8,"native RGB24 conversion")
                    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
                    if previous is not None:
                        reserve(owner,limits,8*8*8*8,"adjacent transition histogram")
                        hist.append(flow_histogram(previous,gray,a-starts[-1],np,cv2,owner,limits))
                        midpoints.append((a+starts[-1])/2)
                    for j,target in enumerate(MIDPOINTS):
                        if a<=target<b:
                            need(frames[j] is None,"unique actual midpoint interval")
                            reserve(owner,limits,size,"retained actual midpoint frame")
                            frames[j]=rgb.copy();frame_indices[j]=len(starts)
                    previous=gray;starts.append(a);ends.append(b)
                elif packet.stream.index==role.audio_stream:
                    a,b=audio_interval(frame,origin);current=tuple(c.name for c in frame.layout.channels)
                    if rate is None:rate=frame.sample_rate;layout=current;audio_start=a
                    need(rate==frame.sample_rate and current==layout and (audio_end is None or a==audio_end),
                         "continuous native audio rate, channel layout and PTS")
                    need(sample_count+frame.samples<=role.max_audio_samples,"native audio extent before conversion")
                    reserve(owner,limits,frame.samples*len(current)*8*3,"normalized native audio frame")
                    audio.append(normalized_audio(frame,np));sample_count+=frame.samples;audio_end=b
                else:
                    raise ValueError("unexpected decoded stream")
        need(len(starts)>=2 and starts[0]<=0 and ends[-1]>=3 and all(f is not None for f in frames),
             "complete authentic visual support and all14 midpoint selections")
        samples=None
        if role.audio_status=="presented_audio":
            need(audio and audio_start<=0 and audio_end>=3,"full actual heard-audio support")
            reserve(owner,limits,sample_count*len(layout)*8,"concatenated native audio")
            samples=np.concatenate(audio,axis=0)
        answer={"frames":frames,"motion":motion_bins(hist,midpoints,np,owner,limits),
                "audio":samples,"audio_rate":rate,"audio_start":audio_start,
                "provenance":{"source_media":role.source_media,"video_id":role.video_id,
                  "audio_status":role.audio_status,"frame_count":len(starts),
                  "frame_starts":[fraction_pair(x) for x in starts],
                  "frame_ends":[fraction_pair(x) for x in ends],
                  "selected_frame_indices":frame_indices,
                  "selected_midpoints":[fraction_pair(x) for x in MIDPOINTS],
                  "audio_start":fraction_pair(audio_start) if audio_start is not None else None,
                  "audio_end":fraction_pair(audio_end) if audio_end is not None else None,
                  "audio_rate":rate,"audio_samples":sample_count,"audio_layout":layout,
                  "flow_transition_midpoints":[fraction_pair(x) for x in midpoints],
                  "flow_boundary":"nearest actual transition estimate, piecewise constant Voronoi support clipped to [0,3)",
                  "clock_domain":"rational container PTS relative to selected origin; no measured presentation/trigger claim"}}
    except BaseException as exc:
        owner.failure(rec,exc)
    finally:
        if container is not None:owner.close(rec,container.close)
        if buffer is not None:owner.close(rec,buffer.close)
    owner.complete(rec)
    return answer


def acoustic_features(samples,rate,start,np,owner,limits):
    """Selected 64-band Slaney logmel plus original30 native RMS/ZCR terms."""
    from scipy.signal import resample_poly
    from stimulus_core import acoustic
    need(samples.ndim==2 and np.isfinite(samples).all(),"complete decoded native heard audio")
    reserve(owner,limits,int(samples.nbytes)+max(len(samples),48000)*8*4,"audio mean and polyphase workspace")
    mono=samples.mean(axis=1)
    divisor=math.gcd(rate,16000)
    resampled=resample_poly(mono,16000//divisor,rate//divisor,window=("kaiser",5.0),padtype="constant",cval=0.0)
    # Resampling preserves first-sample phase. Fractional offset handling is a
    # genuine unsupported clock gate, not rounded index or invented samples.
    index=-start*16000
    need(index.denominator==1 and index>=0,"resampled native clock must contain exact t=0 sample")
    first=int(index)
    need(first+48000<=len(resampled),"complete3s resampled audio, no sample padding repair")
    waveform=resampled[first:first+48000]
    reserve(owner,limits,(48400+300*400+300*201+64*201+300*64)*8*3,"complete mel window/FFT/filter arrays")
    padded=np.pad(waveform,(200,200),mode="reflect")
    windows=np.asarray([padded[j*160:j*160+400] for j in range(300)])
    # Explicit periodic Hann, centers0..2.99s, real power spectrum, no learned fit.
    hann=0.5-0.5*np.cos(2*np.pi*np.arange(400)/400)
    power=np.abs(np.fft.rfft(windows*hann,axis=1))**2
    def hz_to_mel(hz):
        return hz/(200/3) if hz<1000 else 15+math.log(hz/1000)/(math.log(6.4)/27)
    def mel_to_hz(mel):
        return mel*(200/3) if mel<15 else 1000*math.exp((mel-15)*(math.log(6.4)/27))
    edges=np.asarray([mel_to_hz(x) for x in np.linspace(0,hz_to_mel(8000),66)])
    frequency=np.fft.rfftfreq(400,1/16000)
    bank=np.maximum(0,np.minimum((frequency[None,:]-edges[:-2,None])/(edges[1:-1]-edges[:-2])[:,None],
                               (edges[2:,None]-frequency[None,:])/(edges[2:]-edges[1:-1])[:,None]))
    bank*=2/(edges[2:]-edges[:-2])[:,None]
    need((bank.sum(axis=1)>0).all(),"all64 fixed mel bands supported by actual FFT")
    mel=np.log1p(power@bank.T)
    legacy=acoustic(samples,rate,float(start))
    result=np.concatenate((mel.reshape(-1),legacy[:,0],legacy[:,1]))
    need(result.shape==(BLOCK_DIMS["acoustic"],) and np.isfinite(result).all(),"complete finite acoustic features")
    return result


def ocular_features(raw_eye):
    """150 bins x(gazeX,gazeY,pupil,speedX,speedY,speedP,observed,pair).

    Caller supplies joined repeat means before this deterministic expansion;
    missingness fractions remain explicit. No held-person fitted transform.
    """
    import numpy as np
    x=np.asarray(raw_eye)
    need(x.shape==(150,8) and np.isfinite(x).all(),"complete original ocular8 feature order")
    extra=np.column_stack((x[:,0]**2,x[:,1]**2,x[:,2]**2,x[:,0]*x[:,1]))
    result=np.concatenate((x,extra),axis=1).reshape(-1)
    need(result.shape==(1800,) and np.isfinite(result).all(),"all12ocular terms perbin")
    return result


def timing_features(raw_timing):
    import numpy as np
    x=np.asarray(raw_timing)
    need(x.shape==(26,) and np.isfinite(x).all(),"exact26 joined original timing predictors")
    return x


def produce(media_root,source_map,checkpoint_root,checkpoint_descriptor,out,owner,limits):
    """Emit full1102 per-video fixed feature blocks and actual cost/provenance."""
    rec=owner.begin("generalization_complete_fixed_features")
    answer=None;wall=time.monotonic();cpu=time.process_time();start_used=dict(owner.used)
    try:
        need(isinstance(source_map,SourceMap) and tuple(r.video_id for r in source_map.roles)==VIDEO_IDS,
             "complete validated1102 media/source map")
        limits.validate();runtime=modules();np,torch,vision,cv2,scipy,av=runtime
        torch.set_num_threads(1);cv2.setNumThreads(1)
        torch.use_deterministic_algorithms(True)
        encoder=Encoder(checkpoint_root,checkpoint_descriptor,owner,limits,runtime)
        writer=Writer(out,owner);records=[]
        for role in source_map.roles:
            before=dict(owner.used);video_wall=time.monotonic();video_cpu=time.process_time()
            decoded=decode_features(media_root,role,source_map.library_versions,owner,limits,runtime)
            frames=decoded["frames"]
            learned=encoder.vector(frames)
            reverse=encoder.vector(list(reversed(frames)))
            reserve(owner,limits,FEATURE_DIM*8,"complete matched-static accumulator",vector=True)
            static=np.zeros(FEATURE_DIM,dtype=np.float64)
            for frame in frames:
                #14 passes, each14 copies of the same real frame; equal node/dim.
                static+=encoder.vector([frame]*14)
            static/=14
            silent=role.audio_status=="presented_silent_no_track"
            reserve(owner,limits,BLOCK_DIMS["acoustic"]*8,"acoustic full output")
            sound=(np.zeros(BLOCK_DIMS["acoustic"],dtype=np.float64) if silent else
                   acoustic_features(decoded["audio"],decoded["audio_rate"],decoded["audio_start"],np,owner,limits))
            blocks={"matched_static":static,"motion":decoded["motion"],"acoustic":sound,
                    "learned_video":learned,"learned_video_reversed":reverse,
                    "silence":np.asarray([float(silent)],dtype=np.float64)}
            row={"video_id":role.video_id,"arrays":{},"provenance":decoded["provenance"]}
            for name,value in blocks.items():
                need(value.shape==(BLOCK_DIMS[name],) and np.isfinite(value).all(),"full fixed block: "+name)
                row["arrays"][name]=writer.array("video-%04d-%s.npy"%(role.video_id,name),value)
            row["cost"]={"s3d_forward_calls":16,"cpu_seconds":time.process_time()-video_cpu,
                         "wall_seconds":time.monotonic()-video_wall,
                         "logical_delta":{k:owner.used[k]-before[k] for k in before}}
            records.append(row)
        need(encoder.calls==1102*16,"all chronological/reversal/14static forwards executed")
        answer={"schema":"neural080_full_generalization_features_v1","videos":records,
                "blocks":BLOCK_DIMS,"s3d_nodes":list(NODES),"s3d_shapes":[list(s) for s in NODE_SHAPES],
                "checkpoint":checkpoint_descriptor,"runtime_versions":VERSIONS,
                "vision_revision":VISION_REVISION,"opencv_revision":OPENCV_REVISION,
                "canonical_source_map_sha256":source_map.canonical_source_map_sha256,
                "source_evidence":dict(source_map.identity_evidence),
                "limits":vars(limits),"s3d_forward_calls":encoder.calls,
                "silence_count":sum(r.audio_status=="presented_silent_no_track" for r in source_map.roles),
                "feature_fit":"none; FIT-only scaler/PCA is separately nested in readout",
                "cost":{"cpu_seconds":time.process_time()-cpu,"wall_seconds":time.monotonic()-wall,
                        "logical_delta":{k:owner.used[k]-start_used[k] for k in start_used}},
                "resource_scope":"logical cumulative allocation ledger; separately qualified native peak/CPU/isolation required",
                "audio_phase_gate":"native audio after polyphase resampling must contain exact integer16k t=0 sample; otherwise refuse without interpolation",
                "hardware_alignment_verified":False,"empirical_reference_competence_verified":False}
        manifest = writer.document("FULL_FEATURES.json",answer)
        answer = {"manifest":manifest,"features":answer,"output":str(writer.root)}
    except BaseException as exc:
        owner.failure(rec,exc)
    owner.complete(rec)
    return answer
