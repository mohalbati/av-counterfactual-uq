"""
Parameter definitions, with sources and the reasoning behind each derived value.

Every quantity is one of:
  PUBLISHED  - taken directly from a cited paper
  DERIVED    - computed from published numbers (derivation given)
  ASSUMED    - an engineering assumption, stated so it can be challenged; its
               influence is measured in the sensitivity analysis
"""
import numpy as np

G = 9.81  # m/s^2

# --------------------------------------------------------------------------
# NIEON-type response timing (Engstrom, Liu, Dinparastdjadid, Simoiu 2024,
# Accident Analysis & Prevention 198:107460, Section 4.1)
# --------------------------------------------------------------------------
# PUBLISHED: RspT = m + k * RUT, fit to n = 36 SHRP2 rear-end conflicts with
# non-impaired, eyes-on-path drivers; Pearson r = 0.55; p < 0.001.
RT_M = 0.63          # s
RT_K = 0.47          # s per s of ramp-up time
RT_N = 36
RT_R = 0.55
LOOMING_THRESHOLD = 0.05   # rad/s, defines the end of ramp-up (T2)

# DERIVED: standard error of the slope from r and n only,
#   SE(k) = k * sqrt((1 - r^2) / (r^2 (n - 2)))
RT_K_SE = RT_K * np.sqrt((1 - RT_R**2) / (RT_R**2 * (RT_N - 2)))   # ~0.122 s/s
# Check: t = k / SE(k) = 3.85 -> two-sided p ~ 0.0005 < 0.001 (consistent).

# ASSUMED: standard error of the intercept. Not reported; with RUT values
# clustered near zero (fast-developing conflicts) SE(m) is of the same order
# as the residual SD / sqrt(n). We use 0.10 s and test 0.05-0.20 s.
RT_M_SE = 0.10

# DERIVED + ASSUMED: residual scatter. With r = 0.55 the regression explains
# r^2 = 30% of the variance, so residual SD = sqrt(1 - r^2) * SD(RspT)
# = 0.835 * SD(RspT). The paper reports positive skew and heteroscedasticity
# (more scatter at long RUT), so residuals are modelled as multiplicative
# lognormal with coefficient of variation CV. CV is ASSUMED to lie in
# [0.25, 0.55]: for typical mean response times of 0.8-1.5 s this gives a
# residual SD of 0.2-0.8 s, the range implied by SD(RUT) = 0.5-1.5 s.
RT_CV_RANGE = (0.25, 0.55)

# --------------------------------------------------------------------------
# Evasive braking of the reference driver - ASSUMED (the NIEON braking
# profile itself is not published in the reviewed papers). Ranges cover hard
# emergency braking by attentive drivers in modern passenger cars.
# --------------------------------------------------------------------------
NIEON_AMAX_RANGE = (6.5, 8.5)    # m/s^2
NIEON_JERK_RANGE = (10.0, 30.0)  # m/s^3

# --------------------------------------------------------------------------
# Generic, illustrative ADS responder - ASSUMED. NOT Waymo's system.
# Reacts a fixed latency after the lead vehicle starts to decelerate.
# --------------------------------------------------------------------------
ADS_LATENCY_RANGE = (0.30, 0.80)   # s, detection + actuation after LV decel onset
ADS_AMAX_RANGE = (7.0, 9.0)        # m/s^2
ADS_JERK_RANGE = (20.0, 40.0)      # m/s^3

# --------------------------------------------------------------------------
# Reconstruction uncertainty for a police-report-based reconstruction -
# ASSUMED, expressed as relative or absolute half-widths around the nominal
# reconstruction. Scanlon et al. (2021, 2026) note that the documentation
# varies widely between cases; they do not quantify it.
# --------------------------------------------------------------------------
REC_SPEED_REL = 0.10        # +/-10% on initial following speed
REC_HEADWAY_REL = 0.25      # +/-25% on initial time headway
REC_LEAD_DECEL_REL = 0.20   # +/-20% on lead-vehicle deceleration
REC_LEAD_JERK_RANGE = (5.0, 20.0)   # m/s^3, lead vehicle brake ramp

# Geometry - ASSUMED
LEAD_WIDTH = 1.8      # m, lead vehicle width (for visual looming)
EYE_TO_BUMPER = 2.0   # m, driver eye to own front bumper

# --------------------------------------------------------------------------
# Injury risk - DERIVED from TARGET (Campolettano et al., 2025, Traffic
# Safety Research 9): 10% MAIS3+ risk at 126 kph closing speed for
# rear-end car-to-car collisions. TARGET converts delta-v to closing speed by
# momentum conservation (no restitution, equal masses), so delta-v = closing/2
# and the 10% point is at delta-v = 63 kph.
# The slope is not recoverable from the published threshold alone, so it is
# treated as epistemic: the delta-v giving 50% risk is a multiple R50 of the
# 10% delta-v, ASSUMED R50 in [1.3, 1.8].
# --------------------------------------------------------------------------
TARGET_REAR_CLOSING_KPH = 126.0
DV10_KPH = TARGET_REAR_CLOSING_KPH / 2.0
R50_RANGE = (1.3, 1.8)


def injury_risk(closing_speed_ms, r50):
    """P(MAIS3+) for the struck occupant, logistic in delta-v (kph)."""
    dv = np.asarray(closing_speed_ms) * 3.6 / 2.0
    dv50 = DV10_KPH * r50
    b1 = np.log(9.0) / (dv50 - DV10_KPH)
    b0 = -b1 * dv50
    p = 1.0 / (1.0 + np.exp(-(b0 + b1 * dv)))
    return np.where(dv > 0, p, 0.0)
