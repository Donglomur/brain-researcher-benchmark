"""Declared software ABI; exact binary/wheel identities remain external gates."""
def check():
    import sys,importlib.metadata
    from .core import need
    need(sys.version_info[:2]==(3,12),'selected scientific Python3.12')
    need(importlib.metadata.version('numpy')=='2.2.6','selected scientific NumPy2.2.6')
    # Torch/Pillow/Transformers execute in the separately qualified rootfs.
    return {'python':'3.12','numpy':'2.2.6','feature_torch':'2.5.1+cpu',
            'feature_torchvision':'0.20.1+cpu','Pillow':'11.1.0','provider_transformers':'4.46.3',
            'binary_hashes_qualified_by_external_selection':True}

