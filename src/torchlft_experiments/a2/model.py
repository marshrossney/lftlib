from typing import TypeAlias

from jsonargparse.typing import PositiveInt, PositiveFloat, restricted_number_type
import torch
import torch.nn as nn
import torch.nn.functional as F

from torchlft.nflow.model import Model as BaseModel

from torchlft.utils.lattice import laplacian
from torchlft.utils.linalg import dot, mv

Tensor: TypeAlias = torch.Tensor

LatticeDim = restricted_number_type("LatticeDim", int, [("==", 1), ("==", 2)], join="or")


class Model(BaseModel):
    def __init__(
        self,
        lattice_length: PositiveInt,
        lattice_dim: LatticeDim,
        m_sq: PositiveFloat
    ):
        super().__init__(1)
        L, d = lattice_length, lattice_dim
        D = pow(L, d)
        
        self.lattice_size = D
        self.m_sq = m_sq

        K = -laplacian(L, d) + m_sq * torch.eye(D)
        Σ = torch.linalg.inv(K)
        T = torch.linalg.cholesky(Σ)
        self.kernel = K
        self.covariance = Σ
        self.cholesky = T

        weight = torch.empty(D, D).uniform_(0, 1)
        self.register_parameter("weight", nn.Parameter(weight))
        
        mask = torch.ones(D, D).tril().bool()
        self.register_buffer("mask", mask)


    def flow_forward(self, z: Tensor) -> tuple[Tensor, Tensor]:
        T = self.mask * self.weight
        x = mv(T, z)
        log_det_dxdz = T.diag().log().sum().expand(x.shape[0])
        return x, log_det_dxdz


    def base(self, batch_size: PositiveInt) -> tuple[Tensor, Tensor]:
        z = torch.empty(
            size=(batch_size, self.lattice_size),
            device=self.device,
            dtype=self.dtype,
        ).normal_()
        S_z = 0.5 * dot(z, z)
        return z, S_z


    def target(self, φ: Tensor) -> Tensor:
        K = self.kernel
        return 0.5 * dot(φ, mv(K, φ))
