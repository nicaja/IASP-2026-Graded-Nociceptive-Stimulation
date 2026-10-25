"""Linear mixed models for the scalar outcomes and the planned intensity contrasts.

For each outcome and region, sequence-level observations are modelled as

    outcome ~ intensity + recording type + recording order
    random: per-animal intercept and intensity slopes; per-sequence intercept within animal

so repeated sequences add within-animal information without being treated as separate
animals. Contrasts (10x vs 2x, 20x vs 2x, 20x vs 10x MT) get Wald tests and 95% Wald intervals;
Holm correction runs over the nine region-by-contrast tests of each outcome. An animal-level
bootstrap interval is reported alongside.

The REML likelihood is maximised directly through each animal's observation covariance
(two optimisers must agree), because statsmodels' default fitter can fail when an animal-level
variance is estimated at zero. The result is checked against an independent evaluation of the
same likelihood before use.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from statsmodels.formula.api import mixedlm
from statsmodels.regression.mixed_linear_model import MixedLMParams, MixedLMResults, MixedLMResultsWrapper
from statsmodels.stats.multitest import multipletests

SCALAR = ("total", "evoked", "induced", "evoked_fraction")
APERIODIC = ("aperiodic_exponent", "aperiodic_offset", "adjusted_power")
OUTCOMES = SCALAR + APERIODIC
INTENSITY = "C(intensity, Treatment(reference='2x MT'))"


def make_model(table: pd.DataFrame, outcome: str, region: str):
    subset = table.loc[table.region == region].copy()
    return mixedlm(f"{outcome} ~ {INTENSITY} + C(task) + run_order_z", subset, groups=subset.subject,
                   re_formula=f"1 + {INTENSITY}", vc_formula={"block": "0 + C(block_id)"})


class DenseREML:
    """Profiled REML objective evaluated through the observation covariance of each animal.

    A singular animal covariance is allowed: the residual variance keeps every animal's
    observation covariance positive definite, so no random-effect covariance is inverted.
    """

    def __init__(self, model):
        self.model = model
        self.lower = np.tril_indices(model.k_re)
        self.groups = [(model.exog_li[i], model.endog_li[i], model.exog_re_li[i],
                        [mats[i] @ mats[i].T for mats in model.exog_vc.mats])
                       for i in range(model.n_groups)]

    def evaluate(self, covariance, variances, beta=None):
        p = self.model.k_fe
        information, xy = np.zeros((p, p)), np.zeros(p)
        logdet, solved = 0.0, []
        for x, y, z, blocks in self.groups:
            marginal = np.eye(len(y)) + z @ covariance @ z.T
            for variance, block in zip(variances, blocks, strict=True):
                marginal += variance * block
            factor = cho_factor(marginal, lower=True)
            inverse = cho_solve(factor, np.eye(len(y)))
            vx, vy = inverse @ x, inverse @ y
            information += x.T @ vx
            xy += x.T @ vy
            logdet += 2 * np.log(np.diag(factor[0])).sum()
            solved.append((x, y, z, blocks, inverse, vx))
        inverse_info = np.linalg.inv(information)
        if beta is None:
            beta = inverse_info @ xy
        quadratic = sum((y - x @ beta) @ inverse @ (y - x @ beta) for x, y, _, _, inverse, _ in solved)
        df = self.model.n_totobs - p
        scale = quadratic / df
        llf = -0.5 * (logdet + np.linalg.slogdet(information)[1] + df * (np.log(2 * np.pi * scale) + 1))
        grad_g, grad_v, grad_beta = np.zeros_like(covariance), np.zeros_like(variances), np.zeros(p)
        for x, y, z, blocks, inverse, vx in solved:
            residual = inverse @ (y - x @ beta)
            projected = inverse - vx @ inverse_info @ vx.T
            gradient = -0.5 * (projected - np.outer(residual, residual) / scale)
            grad_g += z.T @ gradient @ z
            grad_v += np.array([np.sum(gradient * block) for block in blocks])
            grad_beta += x.T @ residual / scale
        return float(llf), beta, float(scale), grad_g, grad_v, grad_beta

    def objective(self, theta):
        factor = np.zeros((self.model.k_re, self.model.k_re))
        factor[self.lower] = theta[:len(self.lower[0])]
        block_sd = theta[len(self.lower[0]):]
        value = self.evaluate(factor @ factor.T, block_sd ** 2)
        gradient = np.r_[(2 * value[3] @ factor)[self.lower], 2 * block_sd * value[4]]
        return -value[0], -gradient

    def covariance_score(self, params):
        parsed = MixedLMParams.from_packed(params, self.model.k_fe, self.model.k_re, use_sqrt=False, has_fe=True)
        value = self.evaluate(parsed.cov_re, parsed.vcomp, parsed.fe_params)
        gradient = value[3].copy()
        gradient[self.lower] *= np.where(self.lower[0] == self.lower[1], 1.0, 2.0)
        return np.r_[value[5], gradient[self.lower], value[4]]

    def hessian(self, params, relative_step=1e-4):
        step = relative_step * np.maximum(1.0, np.abs(params))
        matrix = np.empty((len(params), len(params)))
        for i in range(len(params)):
            shift = np.zeros(len(params))
            shift[i] = step[i]
            matrix[:, i] = (self.covariance_score(params + shift) - self.covariance_score(params - shift)) / (2 * step[i])
        return (matrix + matrix.T) / 2


def fit(table: pd.DataFrame, outcome: str, region: str):
    """REML fit with two optimisers that must agree; returns a statsmodels results object."""
    model = make_model(table, outcome, region)
    model.reml, model.cov_pen, model.fe_pen, model._freepat = True, None, None, None
    objective = DenseREML(model)
    initial = np.r_[np.eye(model.k_re)[objective.lower], np.ones(model.k_vc)]
    candidates = []
    for method, start in (("BFGS", initial), ("L-BFGS-B", initial * 0.35)):
        options = {"maxiter": 1500, "gtol": 1e-7}
        if method == "L-BFGS-B":
            options.update(ftol=1e-14, maxls=50)
        candidates.append(minimize(objective.objective, start, jac=True, method=method, options=options))
    best = min(candidates, key=lambda result: result.fun)
    if np.linalg.norm(best.jac) > 1e-4 or abs(candidates[0].fun - candidates[1].fun) > 1e-5:
        raise RuntimeError(f"REML optimisers disagree for {outcome} {region}")
    params = MixedLMParams.from_packed(best.x, model.k_fe, model.k_re, use_sqrt=True, has_fe=False)
    llf, beta, scale, grad_g, grad_v, _ = objective.evaluate(params.cov_re, params.vcomp)
    params.fe_params = beta
    packed = params.get_packed(use_sqrt=False, has_fe=True)
    covariance = np.linalg.inv(-objective.hessian(packed))
    covariance_fine = np.linalg.inv(-objective.hessian(packed, relative_step=5e-5))
    se_delta = np.max(np.abs(np.sqrt(np.diag(covariance)[:model.k_fe]) - np.sqrt(np.diag(covariance_fine)[:model.k_fe])))
    # At a boundary (a zero variance) the score need not vanish, but it must not point inwards.
    if max(np.linalg.eigvalsh(grad_g).max(), grad_v.max()) > 1e-4 or se_delta > 1e-5:
        raise RuntimeError(f"Unstable covariance estimate for {outcome} {region}")
    if not np.isfinite(covariance).all() or np.linalg.eigvalsh(covariance[:model.k_fe, :model.k_fe]).min() <= 0:
        raise RuntimeError(f"Invalid fixed-effect covariance for {outcome} {region}")
    result = MixedLMResults(model, packed, covariance / scale)
    result.params_object, result.fe_params = params, beta
    result.cov_re, result.vcomp, result.scale = params.cov_re * scale, params.vcomp * scale, scale
    result.cov_re_unscaled, result.method, result.converged = params.cov_re, "REML", True
    result.hist, result.reml, result.cov_pen = None, True, None
    result.k_fe, result.k_re, result.k_re2, result.k_vc = model.k_fe, model.k_re, model.k_re2, model.k_vc
    result.use_sqrt, result.freepat = True, None
    result._cache = {"llf": llf}
    result = MixedLMResultsWrapper(result)
    check_likelihood(result)
    return result


def check_likelihood(result) -> None:
    """Re-evaluate the REML likelihood and GLS fixed effects independently of the optimiser."""
    model = result.model
    information, score, logdet, groups = np.zeros((model.k_fe, model.k_fe)), np.zeros(model.k_fe), 0.0, []
    for index, _ in enumerate(model.group_labels):
        x, y, z = model.exog_li[index], model.endog_li[index], model.exog_re_li[index]
        covariance = z @ np.asarray(result.cov_re) @ z.T + result.scale * np.eye(len(y))
        for variance, matrices in zip(result.vcomp, model.exog_vc.mats, strict=True):
            covariance += variance * (matrices[index] @ matrices[index].T)
        factor = cho_factor(covariance, lower=True)
        information += x.T @ cho_solve(factor, x)
        score += x.T @ cho_solve(factor, y)
        logdet += 2 * np.log(np.diag(factor[0])).sum()
        groups.append((x, y, factor))
    beta = np.linalg.solve(information, score)
    quadratic = sum((y - x @ beta) @ cho_solve(factor, y - x @ beta) for x, y, factor in groups)
    df = model.n_totobs - model.k_fe
    llf = -0.5 * (logdet + np.linalg.slogdet(information)[1] + quadratic + df * np.log(2 * np.pi))
    if abs(result.llf - llf) > 1e-6 or np.max(np.abs(beta - result.fe_params)) > 1e-7:
        raise RuntimeError("Likelihood check failed")


def bootstrap_interval(table, outcome, region, high, low, seed, samples) -> tuple[float, float]:
    """95% interval from resampling animals; each animal gives its mean within-sequence difference."""
    subset = table.loc[table.region == region]
    means = subset.pivot_table(index=["subject", "block_id"], columns="intensity", values=outcome)
    differences = (means[high] - means[low]).groupby(level="subject").mean().dropna().to_numpy(float)
    rng = np.random.default_rng(seed)
    resampled = rng.choice(differences, size=(samples, len(differences)), replace=True).mean(axis=1)
    return tuple(np.quantile(resampled, [0.025, 0.975]).tolist())


def contrasts(table: pd.DataFrame, outcome: str, config: dict) -> pd.DataFrame:
    rows = []
    seed, samples = config["statistics"]["seed"], config["statistics"]["bootstrap_samples"]
    for ri, region in enumerate(config["design"]["regions"]):
        result = fit(table, outcome, region)
        names = list(result.fe_params.index)
        covariance = result.cov_params().loc[names, names].to_numpy(float)
        estimates = result.fe_params.to_numpy(float)
        subset = table.loc[table.region == region]
        for ci, (contrast, high, low) in enumerate(config["design"]["contrasts"]):
            vector = np.zeros(len(names))
            for level, sign in ((high, 1.0), (low, -1.0)):
                if level != "2x MT":
                    vector[names.index(f"{INTENSITY}[T.{level}]")] += sign
            estimate = float(vector @ estimates)
            se = float(np.sqrt(vector @ covariance @ vector))
            z = estimate / se
            boot_low, boot_high = bootstrap_interval(table, outcome, region, high, low, seed + ri * 10 + ci, samples)
            rows.append({"outcome": outcome, "region": region, "contrast": contrast, "estimate": estimate,
                         "standard_error": se, "wald_ci_low": estimate - 1.96 * se,
                         "wald_ci_high": estimate + 1.96 * se, "statistic_z": z,
                         "p_value": float(2 * stats.norm.sf(abs(z))),
                         "bootstrap_ci_low": boot_low, "bootstrap_ci_high": boot_high,
                         "n_animals": subset.subject.nunique(), "n_blocks": subset.block_id.nunique()})
    output = pd.DataFrame(rows)
    output.insert(output.columns.get_loc("p_value") + 1, "p_holm", multipletests(output.p_value, method="holm")[1])
    return output


def fit_outcome_job(job, config) -> str:
    folder, outcome = Path(job[0]), job[1]
    source = "aperiodic_features.csv" if outcome in APERIODIC else "scalar_features.csv"
    table = pd.read_csv(folder / source, dtype={"subject": str}, float_precision="round_trip")
    if outcome in APERIODIC:
        table = table.loc[table.fit_ok].copy()
    target = folder / f"contrasts_{outcome}.csv"
    contrasts(table, outcome, config).to_csv(target, index=False)
    return str(target)
