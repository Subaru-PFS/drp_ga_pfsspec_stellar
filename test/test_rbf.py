from test.test_base import TestBase
import numpy as np

from pfsspec.rbf import Rbf

class TestRbf(TestBase):

    def test_fit_solve(self):
        x = np.arange(0, 10) - 5.0
        y = np.arange(0, 10) - 5.0
        z = np.arange(0, 10) - 5.0
        di = x**2 + y**2 + z**2

        rbf = Rbf()
        rbf.fit(x, y, z, di)

        y = rbf(0, 0, 0)
        self.assertAlmostEqual(0, y)

    def test_fit_nnls(self):
        x = np.arange(0, 10) - 5.0
        y = np.arange(0, 10) - 5.0
        z = np.arange(0, 10) - 5.0
        di = x**2 + y**2 + z**2

        rbf = Rbf()
        rbf.fit(x, y, z, di, mode='1-D', method='nnls')

        y = rbf(0, 0, 0)
        self.assertAlmostEqual(0, y)