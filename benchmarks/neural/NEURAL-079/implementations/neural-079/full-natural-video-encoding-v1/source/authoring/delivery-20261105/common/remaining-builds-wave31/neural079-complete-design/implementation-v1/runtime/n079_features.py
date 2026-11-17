"""Full17-output prospective extractor; native original programme stays separate."""
import importlib
import os
from n079_common import require, fields, integer, close_all, checked_pin
from n079_plan import NODES, DIMS, D, SHAPES
from n079_arrays import RowFeatureWriter, preflight


def frame_indices(count):
    integer(count, 1)
    # Exact nonnegative linspace floor for14 inclusive points. Short clips
    # preserve every original frame then repeat the final frame.
    return [i * (count - 1) // 13 for i in range(14)] if count >= 14 else list(range(count)) + [count - 1] * (14 - count)


class FeatureExtractor:
    def __init__(self, context, repository, selection, limits):
        context.require_effect('visual_model', 'raw-all17-features')
        fields(selection, ('source_pin', 'weights', 'graph_admission', 'decoder_admission', 'environment_admission',
                           'device', 'max_frames', 'max_pixels', 'max_internal_float_slots'))
        for name in ('source_pin', 'graph_admission', 'decoder_admission', 'environment_admission'):
            checked_pin(selection[name])
        context.join_feature_admission(selection)
        require(selection['device'] in ('cpu', 'cuda'), 'explicit admitted device')
        for name in ('max_frames', 'max_pixels', 'max_internal_float_slots'):
            integer(selection[name], 1)
        require(selection['device'] == 'cpu', 'current complete resource route is CPU-only; GPU requires a separately selected independent resource observer')
        self.context, self.repository, self.selection, self.limits = context, repository, selection, limits
        self.np = importlib.import_module('numpy'); self.torch = importlib.import_module('torch')
        video = importlib.import_module('torchvision.models.video')
        fx = importlib.import_module('torchvision.models.feature_extraction')
        self.av = importlib.import_module('av')
        fd = None; stream = None; error = None
        try:
            fd = repository.open(selection['weights'])
            stream = os.fdopen(fd, 'rb', closefd=True); fd = None
            weights = self.torch.load(stream, map_location='cpu', weights_only=True)
            model = video.s3d(weights=None); model.load_state_dict(weights, strict=True)
            self.model = fx.create_feature_extractor(model, return_nodes={n: n for n in NODES})
            self.model.eval(); self.model.to(selection['device'])
            self.transform = video.S3D_Weights.KINETICS400_V1.transforms()
        except BaseException as exc:
            error = exc; raise
        finally:
            close_all(([('weights stream', stream.close)] if stream is not None else []) +
                      ([('weights descriptor', lambda: os.close(fd))] if fd is not None else []), error)

    def frames(self, admitted_video):
        fields(admitted_video, ('id', 'object', 'frames', 'height', 'width', 'decoder_pin'))
        n = integer(admitted_video['frames'], 1); h = integer(admitted_video['height'], 1); w = integer(admitted_video['width'], 1)
        require(n <= self.selection['max_frames'] and h * w <= self.selection['max_pixels'], 'admitted decoder geometry limits')
        require(admitted_video['decoder_pin'] == self.selection['decoder_admission'], 'exact decoder/color/frame source join')
        indices = frame_indices(n); selected = set(indices)
        require(14 * 3 * h * w <= self.selection['max_internal_float_slots'], 'preventive decoded-frame bound')
        self.context.ledger.charge('raw-all17-features', {'logical_float_slots': 14 * 3 * h * w}, 'complete sampled video frames')
        fd = None; stream = None; container = None; error = None
        try:
            fd = self.repository.open(admitted_video['object'])
            stream = os.fdopen(fd, 'rb', closefd=True); fd = None
            container = self.av.open(stream)
            require(len(container.streams.video) == 1, 'one explicitly admitted visual stream')
            video = container.streams.video[0]; kept = {}; count = 0
            for frame in container.decode(video):
                self.context.tick(); require(count < n and frame.height == h and frame.width == w, 'actual full decoder geometry/order')
                if count in selected:
                    rgb = frame.to_rgb().to_ndarray()
                    require(rgb.shape == (h, w, 3) and rgb.dtype == self.np.uint8, 'exact RGB frame schema')
                    kept[count] = self.torch.from_numpy(rgb).permute(2, 0, 1)
                count += 1
            require(count == n and set(kept) == selected, 'all original frames/selected indices accounted')
            return self.torch.stack([kept[i] for i in indices])
        except BaseException as exc:
            error = exc; raise
        finally:
            close_all(([('video decoder', container.close)] if container is not None else []) +
                      ([('video stream', stream.close)] if stream is not None else []) +
                      ([('video descriptor', lambda: os.close(fd))] if fd is not None else []), error)

    def produce(self, videos, output_fd, lineage):
        require([v['id'] for v in videos] == list(range(1, 1103)), 'full1102 canonical video order')
        preflight(self.limits, 1, D, 3 * D)
        writer = RowFeatureWriter(self.context, output_fd, 'all17-raw-features.f32', 1102, D, '<f4',
                                  self.limits, 'raw-all17-features', lineage)
        error = None
        try:
            with self.torch.no_grad():
                for row, video in enumerate(videos):
                    frames = self.frames(video); tensor = self.transform(frames).unsqueeze(0).to(self.selection['device'])
                    require(tuple(tensor.shape) == (1, 3, 14, 224, 224), 'actual admitted model input')
                    actual = self.model(tensor)
                    require(set(actual) == set(NODES), 'all17 actual graph outputs')
                    start = 0
                    for node, width, shape in zip(NODES, DIMS, SHAPES):
                        value = actual[node]
                        require(value.numel() == width and tuple(value.shape) == (1,) + shape, 'actual full layer extent')
                        # Explicit transfer is the prospective/corrected path;
                        # never claimed byte-identical to original CUDA code.
                        array = value.detach().to('cpu').numpy().reshape(-1)
                        require(array.dtype == self.np.float32, 'source float32 activation dtype')
                        writer.append_feature(row, start, array); start += width
                    self.context.tick()
            return writer.finish()
        except BaseException as exc:
            error = exc; raise
        finally:
            writer.close(error)
