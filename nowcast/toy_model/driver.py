"""Toy nowcast model driver — phase 1: coordinates + blank data structure."""

import glob
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
import cvxlab as cl

phase = sys.argv[1] if len(sys.argv) > 1 else "blank"

m = cl.Model(
    model_dir_name="model",
    main_dir_path=os.getcwd(),
    model_settings_from="yml",
    use_existing_data=False,
    log_level="warning",
)

if phase == "blank":
    m.initialize_model_environment()
    print("MODEL ENVIRONMENT OK")
    print("files:", sorted(os.path.basename(p) for p in glob.glob("model/*")))
elif phase == "run":
    m.initialize_model_environment()
    m.refresh_database_and_initialize_problem(force_overwrite=True)
    print("PROBLEMS INITIALIZED")
    m.run_model(solver="HIGHS", solver_verbose=False)
    m.load_results_to_database(force_overwrite=True)
    print("SOLVED. status:", m.is_problem_solved)
    for name in ("x", "V", "Y_f", "IM_f"):
        v = m.variable(name)
        print(f"  {name} =\n{v}")
