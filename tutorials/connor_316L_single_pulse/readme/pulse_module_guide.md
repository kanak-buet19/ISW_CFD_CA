# Pulsed Laser Module Guide

This solver reads the base laser power from:

```cpp
constant/timeVsLaserPower
```

If pulsing is disabled, that table is used directly.

If pulsing is enabled, the table is treated as the base laser power envelope. Pulsing is applied only when the table value is active.

## Basic Setup

Add pulse settings in:

```cpp
constant/LaserProperties
```

Example for Connor/Riffel 316L paper parameters:

```cpp
pulseLaser true;
pulseFrequency 10;
pulseDuration 0.0071;
pulseOffPower 0;

pulseShape square;
pulsePowerMode peak;
```

Paper values:

```text
Peak power      1050 W
Pulse duration  7.1 ms
Frequency       10 Hz
Wavelength      1070 nm
Spot size       191 um diameter
```

Use:

```cpp
wavelength 1.070e-6;
laserRadius 95.5e-6;
```

## Power Envelope

`timeVsLaserPower` gives the base power.

Example:

```cpp
(
    (0       1050)
    (0.7125  1050)
    (0.713   0)
)
```

This means the scan has 1050 W available from `0` to `0.7125 s`.

When `pulseLaser true`, the solver applies pulse modulation inside that active region.

## Required Parameters

```cpp
pulseLaser true;
```

Enables pulse mode.

```cpp
pulseFrequency 10;
```

Pulse frequency in Hz.

```cpp
pulseDuration 0.0071;
```

ON-time of each pulse in seconds.

For `10 Hz`:

```text
pulsePeriod = 1 / 10 = 0.1 s
```

For `pulseDuration 0.0071`:

```text
dutyCycle = 0.0071 / 0.1 = 0.071
```

## Optional Parameters

```cpp
pulseOffPower 0;
```

Power during OFF part of pulse. Default is `0`.

```cpp
pulsePhase 0;
```

Time offset for pulse alignment. Default is `0`.

Example:

```cpp
pulsePhase 0.05;
```

shifts the pulse cycle by `0.05 s`.

## Pulse Shapes

Select with:

```cpp
pulseShape square;
```

Available shapes:

```cpp
square
onOff
linearRamp
cosineRamp
gaussian
```

### square / onOff

Direct ON/OFF pulse.

```text
OFF -> full power -> OFF
```

No ramping.

### linearRamp

Linear ramp up and ramp down.

```text
OFF -> linear up -> full power -> linear down -> OFF
```

### cosineRamp

Smooth ramp up and down using a cosine curve.

Better than linear if you want smoother power transitions.

### gaussian

Bell-shaped pulse.

Uses:

```cpp
pulseGaussianSigma
```

If not given, default is:

```text
pulseDuration / 6
```

## Ramp Parameters

For ramped shapes, use fractions:

```cpp
pulseRampUpFraction 0.1;
pulseRampDownFraction 0.1;
```

These are fractions of `pulseDuration`.

Example:

```cpp
pulseDuration 0.0071;
pulseRampUpFraction 0.1;
```

gives:

```text
rampUp = 0.1 * 0.0071 = 0.00071 s
```

Absolute ramp times are also supported:

```cpp
pulseRampUp 0.00071;
pulseRampDown 0.00071;
```

If both are provided, fraction values take priority.

## Power Mode

Select with:

```cpp
pulsePowerMode peak;
```

Available modes:

```cpp
peak
average
```

### peak

`timeVsLaserPower` is interpreted as peak ON-pulse power.

Example:

```text
basePower = 1050 W
dutyCycle = 0.071
```

The pulse peak is `1050 W`, so time-averaged power is lower:

```text
averagePower = 1050 * 0.071 = 74.55 W
```

This matches paper parameters when the paper reports peak pulse power.

### average

`timeVsLaserPower` is interpreted as target time-averaged power.

The solver boosts the pulse peak so total time-integrated energy is conserved.

Example:

```text
basePower = 1050 W
dutyCycle = 0.071
```

For square pulse:

```text
peakPower = 1050 / 0.071 = 14788.7 W
```

Use this only if your input power represents average power, not peak pulse power.

## Recommended Paper Setup

For the provided pulsed LBW paper values:

```cpp
timeVsLaserPower
{
    file "$FOAM_CASE/constant/timeVsLaserPower";
    outOfBounds clamp;
}

pulseLaser true;
pulseFrequency 10;
pulseDuration 0.0071;
pulseOffPower 0;

pulseShape square;
pulsePowerMode peak;

wavelength 1.070e-6;
laserRadius 95.5e-6;
```

Use `pulsePowerMode peak` because the paper lists `Peak pulse power = 1050 W`.

## Plotting Pulse Shapes

Run:

```bash
cd readme
python3 plot_pulse_modes.py
```

Outputs:

```text
readme/pulse_mode/
readme/single_pulse_mode/
```

`pulse_mode` shows several pulse periods.

`single_pulse_mode` zooms into one pulse.

