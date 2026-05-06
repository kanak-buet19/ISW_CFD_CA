#!/usr/bin/env python3

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt


PEAK_POWER = 1050.0
PULSE_FREQUENCY = 10.0
PULSE_DURATION = 7.1e-3
PULSE_OFF_POWER = 0.0
RAMP_UP_FRACTION = 0.1
RAMP_DOWN_FRACTION = 0.1
RAMP_UP = RAMP_UP_FRACTION * PULSE_DURATION
RAMP_DOWN = RAMP_DOWN_FRACTION * PULSE_DURATION
GAUSSIAN_SIGMA = PULSE_DURATION / 6.0

PULSE_PERIOD = 1.0 / PULSE_FREQUENCY
TIME_END = 3.0 * PULSE_PERIOD
N_POINTS = 6000


def pulse_multiplier(t, shape):
    pulse_time = np.mod(t, PULSE_PERIOD)
    active = pulse_time < PULSE_DURATION
    multiplier = np.zeros_like(t)

    if shape in ("square", "onOff"):
        multiplier[active] = 1.0

    elif shape == "linearRamp":
        multiplier[active] = 1.0
        up = active & (pulse_time < RAMP_UP)
        down = active & (pulse_time > PULSE_DURATION - RAMP_DOWN)
        multiplier[up] = pulse_time[up] / RAMP_UP
        multiplier[down] = (PULSE_DURATION - pulse_time[down]) / RAMP_DOWN

    elif shape == "cosineRamp":
        multiplier[active] = 1.0
        up = active & (pulse_time < RAMP_UP)
        down = active & (pulse_time > PULSE_DURATION - RAMP_DOWN)
        multiplier[up] = 0.5 * (1.0 - np.cos(np.pi * pulse_time[up] / RAMP_UP))
        t_down = (PULSE_DURATION - pulse_time[down]) / RAMP_DOWN
        multiplier[down] = 0.5 * (1.0 - np.cos(np.pi * t_down))

    elif shape == "gaussian":
        center = 0.5 * PULSE_DURATION
        multiplier[active] = np.exp(
            -0.5 * ((pulse_time[active] - center) / GAUSSIAN_SIGMA) ** 2
        )

    else:
        raise ValueError(f"Unknown shape: {shape}")

    return multiplier


def average_multiplier(shape):
    t = np.linspace(0.0, PULSE_PERIOD, N_POINTS)
    return np.trapezoid(pulse_multiplier(t, shape), t) / PULSE_PERIOD


def pulse_power(t, shape, mode):
    multiplier = pulse_multiplier(t, shape)

    if mode == "peak":
        scaled = multiplier
    elif mode == "average":
        scaled = multiplier / average_multiplier(shape)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    return PULSE_OFF_POWER + (PEAK_POWER - PULSE_OFF_POWER) * scaled


def main():
    out_dir = Path(__file__).resolve().parent / "pulse_mode"
    single_dir = Path(__file__).resolve().parent / "single_pulse_mode"
    out_dir.mkdir(parents=True, exist_ok=True)
    single_dir.mkdir(parents=True, exist_ok=True)

    t = np.linspace(0.0, TIME_END, N_POINTS)
    t_ms = t * 1e3
    single_time_end = min(PULSE_PERIOD, 1.25 * PULSE_DURATION)
    single_t = np.linspace(0.0, single_time_end, N_POINTS)
    single_t_ms = single_t * 1e3

    shapes = ["square", "linearRamp", "cosineRamp", "gaussian"]
    mode = "peak"

    plt.figure(figsize=(10, 5))
    for shape in shapes:
        plt.plot(t_ms, pulse_power(t, shape, mode), label=shape)

    plt.xlabel("Time [ms]")
    plt.ylabel("Laser power [W]")
    plt.title("Pulse shapes, pulsePowerMode peak")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "pulse_shapes_peak.png", dpi=200)
    plt.close()

    for shape in shapes:
        plt.figure(figsize=(10, 5))
        plt.plot(t_ms, pulse_power(t, shape, mode), label=shape)

        plt.xlabel("Time [ms]")
        plt.ylabel("Laser power [W]")
        plt.title(f"{shape}, pulsePowerMode peak")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / f"{shape}_peak.png", dpi=200)
        plt.close()

    plt.figure(figsize=(10, 5))
    for shape in shapes:
        plt.plot(single_t_ms, pulse_power(single_t, shape, mode), label=shape)

    plt.axvline(PULSE_DURATION * 1e3, color="k", linestyle="--", linewidth=1)
    plt.xlabel("Time within one pulse [ms]")
    plt.ylabel("Laser power [W]")
    plt.title("Single pulse shapes, pulsePowerMode peak")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(single_dir / "single_pulse_shapes_peak.png", dpi=200)
    plt.close()

    for shape in shapes:
        plt.figure(figsize=(10, 5))
        plt.plot(single_t_ms, pulse_power(single_t, shape, mode), label=shape)

        plt.axvline(PULSE_DURATION * 1e3, color="k", linestyle="--", linewidth=1)
        plt.xlabel("Time within one pulse [ms]")
        plt.ylabel("Laser power [W]")
        plt.title(f"Single {shape} pulse, pulsePowerMode peak")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(single_dir / f"single_{shape}_peak.png", dpi=200)
        plt.close()

    summary = out_dir / "pulse_parameters.txt"
    summary.write_text(
        "\n".join(
            [
                f"peakPower_W {PEAK_POWER}",
                f"pulseFrequency_Hz {PULSE_FREQUENCY}",
                f"pulsePeriod_s {PULSE_PERIOD}",
                f"pulseDuration_s {PULSE_DURATION}",
                f"dutyCycle {PULSE_DURATION / PULSE_PERIOD}",
                f"pulseOffPower_W {PULSE_OFF_POWER}",
                f"rampUpFraction {RAMP_UP_FRACTION}",
                f"rampDownFraction {RAMP_DOWN_FRACTION}",
                f"rampUp_s {RAMP_UP}",
                f"rampDown_s {RAMP_DOWN}",
                f"gaussianSigma_s {GAUSSIAN_SIGMA}",
            ]
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
