"""Generated tensor/model doubles only: no Torch/model/native-image execution."""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "selection_features.py"
spec = importlib.util.spec_from_file_location("mindbridge_selection_features_test", SOURCE)
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


class Tensor:
    def __init__(self, data, device="cpu"):
        self.data = np.asarray(data)
        self.device = device

    @property
    def shape(self): return self.data.shape
    @property
    def ndim(self): return self.data.ndim
    @property
    def dtype(self): return self.data.dtype
    def is_floating_point(self): return self.data.dtype.kind == "f"
    def all(self): return self.data.all()
    def any(self): return self.data.any()
    def float(self): return Tensor(self.data.astype("float32"), self.device)
    def to(self, device): return Tensor(self.data, device)
    def unsqueeze(self, axis): return Tensor(np.expand_dims(self.data, axis), self.device)
    def reshape(self, *shape): return Tensor(self.data.reshape(*shape), self.device)
    def __getitem__(self, item): return Tensor(self.data[item], self.device)
    def __lt__(self, other): return Tensor(self.data < other, self.device)
    def __le__(self, other): return Tensor(self.data <= other, self.device)
    def __gt__(self, other): return Tensor(self.data > other, self.device)
    def __truediv__(self, other): return Tensor(self.data / other.data, self.device)
    def detach(self): return self
    def cpu(self): return Tensor(self.data)
    def numpy(self): return self.data


class Encoder:
    """Explicit nonlearned outputs; layers deliberately do not commute."""
    def __init__(self):
        self.config = SimpleNamespace(image_size=224, patch_size=14,
                                      hidden_size=1024, projection_dim=768)
        self.training = False
        self.params = [SimpleNamespace(requires_grad=False, dtype=np.dtype("float32"), device="cpu")]
        self.children = [self]
        self.calls = []
        self.hidden = Tensor(np.broadcast_to(
            np.arange(257, dtype="float32")[None, :, None], (1, 257, 1024)).copy())
        self.vision_model = SimpleNamespace(post_layernorm=self.post)
        self.projected = None
        self.corruption = None

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        raise AssertionError("model construction/download must never occur")

    def modules(self): return self.children
    def parameters(self): return self.params
    def __call__(self, pixels):
        self.calls.append(("encoder", pixels.dtype, pixels.shape))
        return SimpleNamespace(last_hidden_state=self.hidden)
    def post(self, value):
        self.calls.append(("post", value.shape))
        if self.corruption == "post-shape": return Tensor(np.zeros((1, 256, 1024), dtype="float32"))
        if self.corruption == "post-nan": return Tensor(np.full(value.shape, np.nan, dtype="float32"))
        return Tensor(value.data + 1)
    def visual_projection(self, value):
        self.calls.append(("project", value.shape))
        data = value.data[:, :, :768] * 2
        if self.corruption == "projection-shape": data = data[:, :, :767]
        if self.corruption == "projection-nan": data[0, 1, 0] = np.nan
        if self.corruption == "zero-cls": data[:, 0] = 0
        self.projected = Tensor(data)
        return self.projected


def backend():
    torch = ModuleType("torch")
    torch.__version__ = "2.0.1+cpu"
    torch.Tensor = Tensor
    torch.float32, torch.float64 = np.dtype("float32"), np.dtype("float64")
    torch.isfinite = lambda value: Tensor(np.isfinite(value.data))
    torch.norm = lambda value, dim: Tensor(np.linalg.norm(value.data, axis=dim))
    torch.is_autocast_enabled = lambda: False
    torch.is_autocast_cpu_enabled = lambda: False
    grad = {"active": False}
    @contextmanager
    def no_grad():
        grad["active"] = True
        try: yield
        finally: grad["active"] = False
    torch.no_grad = no_grad
    calls = []
    class Resize:
        def __init__(self, size, **kwargs):
            calls.append(("resize-init", size, kwargs))
        def __call__(self, value):
            if not grad["active"]: raise AssertionError("missing no_grad context")
            calls.append(("resize", value.dtype, value.shape))
            return value
    class CenterCrop:
        def __init__(self, size): calls.append(("crop-init", size))
        def __call__(self, value):
            calls.append(("crop", value.dtype))
            return Tensor(np.zeros((1, 3, 224, 224), dtype=value.dtype), value.device)
    class Normalize:
        def __init__(self, **kwargs): calls.append(("normalize-init", kwargs))
        def __call__(self, value):
            calls.append(("normalize", value.dtype))
            return value
    vision = ModuleType("torchvision")
    vision.__version__ = "0.15.2+cpu"
    vision.transforms = SimpleNamespace(Resize=Resize, CenterCrop=CenterCrop, Normalize=Normalize,
                                       InterpolationMode=SimpleNamespace(BICUBIC="bicubic"))
    transformers = ModuleType("transformers")
    transformers.__version__ = "4.generated-control"
    transformers.CLIPVisionModelWithProjection = Encoder
    return {"torch": torch, "torchvision": vision, "transformers": transformers}, calls


class SelectionFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.modules, self.transforms = backend()
        self.patcher = mock.patch.dict(sys.modules, self.modules)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.encoder = Encoder()
        self.image = Tensor(np.full((3, 225, 448), 0.5, dtype="float32"))

    def extract(self, image=None, encoder=None, **kwargs):
        options = {"image_role": "target", "expected_transformers_version": "4.generated-control",
                   "max_input_pixels": 225 * 448}
        options.update(kwargs)
        return selection.extract_selection_features(self.image if image is None else image,
            self.encoder if encoder is None else encoder, **options)

    def test_shared_cls_scaling_after_post_layernorm_and_projection(self):
        result = self.extract()
        tokens = result["selection"]
        self.assertEqual(tokens.shape, (257, 768))
        self.assertEqual(tokens.dtype, np.dtype("float32"))
        np.testing.assert_allclose(np.linalg.norm(tokens, axis=1), np.arange(1, 258), rtol=2e-6)
        self.assertEqual([x[0] for x in self.encoder.calls], ["encoder", "post", "project"])
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["model_weight_identity_verified"])
        self.assertFalse(result["generation_freeze_or_target_isolation_verified"])
        self.assertEqual(result["historical_transformers_runtime_identity"], "unresolved")

    def test_bicubic_crop_normalize_order_and_explicit_legacy_antialias(self):
        self.extract()
        self.assertEqual([x[0] for x in self.transforms],
                         ["resize-init", "resize", "crop-init", "crop", "normalize-init", "normalize"])
        self.assertEqual(self.transforms[0], ("resize-init", 224,
                         {"interpolation": "bicubic", "antialias": None}))
        self.assertEqual(self.transforms[2], ("crop-init", (224, 224)))
        self.assertEqual(self.transforms[4], ("normalize-init",
                         {"mean": selection.CLIP_MEAN, "std": selection.CLIP_STD}))
        self.assertEqual(self.encoder.calls[0][2], (1, 3, 224, 224))

    def test_candidate_float_cast_before_resize_target_dtype_preserved(self):
        image = Tensor(self.image.data.astype("float64"))
        self.extract(image=image, image_role="candidate")
        self.assertEqual(self.transforms[1][1], np.dtype("float32"))
        self.transforms.clear()
        self.extract(image=image, image_role="target")
        self.assertEqual(self.transforms[1][1], np.dtype("float64"))
        self.assertEqual(image.dtype, np.dtype("float64"))

    def test_half_candidate_cast_is_explicit_but_half_target_rejected(self):
        image = Tensor(self.image.data.astype("float16"))
        self.extract(image=image, image_role="candidate")
        with self.assertRaises(selection.SelectionFeatureError): self.extract(image=image)

    def test_bad_roles_and_pixel_bounds_reject_before_model(self):
        for kwargs in ({"image_role": True}, {"image_role": "metric"}, {"max_input_pixels": True},
                       {"max_input_pixels": 0}, {"max_input_pixels": 225 * 448 - 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(selection.SelectionFeatureError):
                self.extract(**kwargs)
        self.assertEqual(self.encoder.calls, [])
        self.assertEqual(self.transforms, [])

    def test_nonfinite_out_of_range_and_non_rgb_inputs_rejected(self):
        values = [np.full((3, 2, 2), x, dtype="float32") for x in (np.nan, np.inf, -.1, 1.1)]
        values += [np.zeros((1, 3, 2, 2), dtype="float32"), np.zeros((4, 2, 2), dtype="float32"),
                   np.zeros((3, 0, 2), dtype="float32"), np.zeros((3, 2, 2), dtype="uint8")]
        for value in values:
            with self.subTest(shape=value.shape), self.assertRaises(selection.SelectionFeatureError):
                self.extract(image=Tensor(value))
        self.assertEqual(self.encoder.calls, [])

    def test_source_tensor_runtime_and_explicit_hf_version_are_enforced(self):
        for module, wrong in (("torch", "2.1.0"), ("torchvision", "0.16.0"),
                              ("transformers", "4.different")):
            with mock.patch.object(self.modules[module], "__version__", wrong):
                with self.assertRaises(selection.SelectionFeatureError): self.extract()
        for value in (None, "", " ", 7):
            with self.assertRaises(selection.SelectionFeatureError):
                self.extract(expected_transformers_version=value)
        self.assertEqual(self.encoder.calls, [])

    def test_autocast_rejected_for_cpu_and_device(self):
        for name in ("is_autocast_enabled", "is_autocast_cpu_enabled"):
            with mock.patch.object(self.modules["torch"], name, return_value=True):
                with self.assertRaises(selection.SelectionFeatureError): self.extract()

    def test_encoder_class_and_all_vit_geometry_fields_required(self):
        with self.assertRaises(selection.SelectionFeatureError): self.extract(encoder=object())
        for key in ("image_size", "patch_size", "hidden_size", "projection_dim"):
            original = getattr(self.encoder.config, key)
            for bad in (True, original + 1, None):
                setattr(self.encoder.config, key, bad)
                with self.assertRaises(selection.SelectionFeatureError): self.extract()
            setattr(self.encoder.config, key, original)
        self.assertEqual(self.encoder.calls, [])

    def test_model_frozen_eval_device_and_dtype_requirements(self):
        self.encoder.children.append(SimpleNamespace(training=True))
        with self.assertRaises(selection.SelectionFeatureError): self.extract()
        self.encoder.children.pop()
        parameter = self.encoder.params[0]
        for key, bad in (("requires_grad", True), ("dtype", np.dtype("float16"))):
            old = getattr(parameter, key); setattr(parameter, key, bad)
            with self.assertRaises(selection.SelectionFeatureError): self.extract()
            setattr(parameter, key, old)
        self.encoder.params.append(SimpleNamespace(requires_grad=False, dtype=np.dtype("float32"), device="cuda"))
        with self.assertRaises(selection.SelectionFeatureError): self.extract()
        self.encoder.params = []
        with self.assertRaises(selection.SelectionFeatureError): self.extract()
        self.assertEqual(self.encoder.calls, [])

    def test_hidden_shape_and_nonfinite_values_rejected(self):
        for data in (np.zeros((1, 256, 1024), dtype="float32"),
                     np.full((1, 257, 1024), np.inf, dtype="float32"),
                     np.zeros((1, 257, 1024), dtype="float16")):
            self.encoder.hidden = Tensor(data)
            with self.assertRaises(selection.SelectionFeatureError): self.extract()
            self.assertNotIn("post", [x[0] for x in self.encoder.calls])
            self.encoder.calls.clear()

    def test_invalid_post_layernorm_or_projection_fails_closed(self):
        for corruption in ("post-shape", "post-nan", "projection-shape", "projection-nan"):
            self.encoder.corruption = corruption
            with self.subTest(corruption=corruption), self.assertRaises(selection.SelectionFeatureError):
                self.extract()

    def test_zero_cls_norm_is_not_repaired_with_epsilon(self):
        self.encoder.corruption = "zero-cls"
        with self.assertRaisesRegex(selection.SelectionFeatureError, "CLS norm"):
            self.extract()

    def test_result_does_not_alias_supplied_model_output(self):
        result = self.extract()
        before = result["selection"].copy()
        self.encoder.projected.data[:] = 0
        np.testing.assert_array_equal(result["selection"], before)


if __name__ == "__main__":
    unittest.main()
