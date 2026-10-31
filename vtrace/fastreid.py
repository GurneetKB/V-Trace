"""Pretrained vehicle Re-ID model from FastReID (JDAI-CV), the framework released by the VeRi-776 authors' team.

We use their published VeRi-776 checkpoint as-is (no training of our own):
    SBS(R50-ibn), VeRi-776: Rank-1 97.0 %, mAP 81.9 %  (FastReID MODEL_ZOO)
    https://github.com/JDAI-CV/fast-reid/releases/download/v0.1.1/veri_sbs_R50-ibn.pth

FastReID itself is a large training framework, so this file only re-declares the network the checkpoint was saved
from (ResNet-50 with IBN-a and non-local blocks, GeM pooling, BN-neck) so the weights load with plain PyTorch.
The output is a 2048-d embedding per vehicle crop; cosine similarity between embeddings = same-vehicle likelihood.
"""
import cv2
import numpy as np
import torch
from torch import nn

from . import config

URL = "https://github.com/JDAI-CV/fast-reid/releases/download/v0.1.1/veri_sbs_R50-ibn.pth"
INPUT_SIZE = (256, 256)                       # (h, w) used by the VeRi config


class IBN(nn.Module):
    """Half InstanceNorm, half BatchNorm (IBN-a)."""
    def __init__(self, planes):
        super().__init__()
        self.half = planes // 2
        self.IN = nn.InstanceNorm2d(self.half, affine=True)
        self.BN = nn.BatchNorm2d(planes - self.half)

    def forward(self, x):
        a, b = torch.split(x, [self.half, x.size(1) - self.half], 1)
        return torch.cat([self.IN(a.contiguous()), self.BN(b.contiguous())], 1)


class Bottleneck(nn.Module):
    def __init__(self, inplanes, planes, ibn, stride=1, downsample=None):
        super().__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, 1, bias=False)
        self.bn1 = IBN(planes) if ibn else nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, 3, stride, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, 1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample

    def forward(self, x):
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        return self.relu(out + (self.downsample(x) if self.downsample is not None else x))


class NonLocal(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.g, self.theta, self.phi = (nn.Conv2d(c, 1, 1) for _ in range(3))
        self.W = nn.Sequential(nn.Conv2d(1, c, 1), nn.BatchNorm2d(c))

    def forward(self, x):
        b = x.size(0)
        g = self.g(x).view(b, 1, -1).permute(0, 2, 1)
        f = torch.matmul(self.theta(x).view(b, 1, -1).permute(0, 2, 1), self.phi(x).view(b, 1, -1))
        y = torch.matmul(f / f.size(-1), g).permute(0, 2, 1).contiguous().view(b, 1, *x.shape[2:])
        return self.W(y) + x


class Backbone(nn.Module):
    LAYERS, NL_IDX = [3, 4, 6, 3], {2: [2, 3], 3: [3, 4, 5]}    # non-local blocks after these layer2/3 blocks

    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 64, 7, 2, 3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(3, 2, 1, ceil_mode=True)
        self.inplanes = 64
        for i, (planes, n, stride) in enumerate(zip([64, 128, 256, 512], self.LAYERS, [1, 2, 2, 1]), 1):
            setattr(self, f"layer{i}", self._make_layer(planes, n, stride, ibn=i < 4))   # last stride 1
        self.NL_2 = nn.ModuleList(NonLocal(512) for _ in self.NL_IDX[2])
        self.NL_3 = nn.ModuleList(NonLocal(1024) for _ in self.NL_IDX[3])

    def _make_layer(self, planes, n, stride, ibn):
        down = None
        if stride != 1 or self.inplanes != planes * 4:
            down = nn.Sequential(nn.Conv2d(self.inplanes, planes * 4, 1, stride, bias=False), nn.BatchNorm2d(planes * 4))
        blocks = [Bottleneck(self.inplanes, planes, ibn, stride, down)]
        self.inplanes = planes * 4
        blocks += [Bottleneck(self.inplanes, planes, ibn) for _ in range(1, n)]
        return nn.Sequential(*blocks)

    def forward(self, x):
        x = self.maxpool(self.relu(self.bn1(self.conv1(x))))
        x = self.layer1(x)
        for li in (2, 3):
            nl, k = getattr(self, f"NL_{li}"), 0
            for i, block in enumerate(getattr(self, f"layer{li}")):
                x = block(x)
                if k < len(nl) and i == self.NL_IDX[li][k]:
                    x, k = nl[k](x), k + 1
        return self.layer4(x)


class Head(nn.Module):
    def __init__(self):
        super().__init__()
        self.pool_layer = nn.Module()
        self.pool_layer.p = nn.Parameter(torch.ones(1) * 3)             # GeM pooling exponent (learned)
        self.bottleneck = nn.Sequential(nn.BatchNorm2d(2048))

    def forward(self, x):
        p = self.pool_layer.p
        x = nn.functional.adaptive_avg_pool2d(x.clamp(min=1e-6).pow(p), 1).pow(1.0 / p)
        return self.bottleneck(x)[..., 0, 0]


class VehicleReID(nn.Module):
    def __init__(self):
        super().__init__()
        self.register_buffer("pixel_mean", torch.zeros(1, 3, 1, 1))
        self.register_buffer("pixel_std", torch.ones(1, 3, 1, 1))
        self.backbone = Backbone()
        self.heads = Head()

    def forward(self, x):                                   # x: RGB float 0..255, (N, 3, 256, 256)
        return self.heads(self.backbone((x - self.pixel_mean) / self.pixel_std))


def load(device="cpu"):
    path = config.REID_WEIGHTS
    if not path.exists():                                   # first run (e.g. on Streamlit Cloud): fetch the release
        torch.hub.download_url_to_file(URL, str(path))
    state = torch.load(path, map_location="cpu", weights_only=False)["model"]
    model = VehicleReID()
    missing, _ = model.load_state_dict(state, strict=False)   # extra keys = training-only classifier
    if missing:
        raise RuntimeError(f"FastReID checkpoint is missing {missing[:5]}")
    return model.eval().to(device)


@torch.no_grad()
def embed(model, crops_bgr, device="cpu", batch=32):
    """L2-normalised 2048-d Re-ID embeddings for a list of BGR crops."""
    out = []
    for i in range(0, len(crops_bgr), batch):
        imgs = [cv2.resize(cv2.cvtColor(c, cv2.COLOR_BGR2RGB), INPUT_SIZE[::-1], interpolation=cv2.INTER_CUBIC)
                for c in crops_bgr[i:i + batch]]
        x = torch.from_numpy(np.stack(imgs)).permute(0, 3, 1, 2).float().to(device)
        out.append(nn.functional.normalize(model(x), dim=1).cpu().numpy())
    return np.concatenate(out).astype(np.float32)
