"""Re-solve and inspect the toy solution against expectations."""

import os

import numpy as np

os.chdir(os.path.dirname(os.path.abspath(__file__)))
import cvxlab as cl

m = cl.Model(model_dir_name="model", main_dir_path=os.getcwd(),
             model_settings_from="yml", use_existing_data=True, log_level="warning")
m.run_model(solver="HIGHS", solver_verbose=False)

def v(name):
    out = m.variable(name, scenario_key=0)
    return np.asarray(out.value if hasattr(out, "value") else out).squeeze()

x = v("x"); U = m.variable("U_f", scenario_key=0); U = np.asarray(U.value if hasattr(U, "value") else U)
V = v("V"); Yf = v("Y_f"); Ynf = v("Y_nf"); IMf = v("IM_f")

print("x  [steel, power, services] =", np.round(x, 2), " (prior [100, 50, 200]; power band 53.9-56.1)")
print("U_f rows [COAL, ELE] x acts =\n", np.round(U, 2), " (prior [[60,25,0],[2,0,20]]; obs +10%)")
print("coal steel (b1211 band 64.7-67.3):", round(float(U[0, 0]), 2))
print("coal total (b121 band 91.6-95.4): ", round(float(U[0, 0] + U[0, 1]), 2))
print("ele steel (b1211 band 2.16-2.24): ", round(float(U[1, 0]), 2))
print("Y_f [COAL, ELE] =", np.round(Yf, 2), " (ELE band 28.4-29.6; prior [2, 27])")
print("Y_nf [STEEL, SERV] =", np.round(Ynf, 2), " (prior [30, 150])")
print("V =", np.round(V, 2), " sum =", round(float(V.sum()), 2), " (GDP band 189.2-200.9)")
print("IM_f [COAL, ELE] =", np.round(IMf, 2), " (coal ≈ its total use, im_sh=1)")
# balances residual check (fuel side): s_f@x + IM_f == U_f@1 + Y_f + EXP_f
s_f = np.array([[0, 0, 0], [0, 1, 0]]); EXPf = np.array([0.0, 1.0])
res = s_f @ x + IMf - (U.sum(axis=1) + Yf + EXPf)
print("fuel balance residual:", np.round(res, 8))
