# Connor 316L Single Pulse Case

This case is a compact single-pulse version of `Connor_316L_base`.

## Purpose

The domain is reduced to cover one Connor/Riffel 316L laser pulse and the local
cooling that follows it. The pulsed laser model keeps the original Connor
parameters:

- peak power: 1050 W
- pulse duration: 0.0071 s
- nominal pulse frequency: 10 Hz
- laser radius: 95.5e-6 m
- scan speed: 4 mm/s, matching the base Connor case

The run ends at `0.0571 s`: one 7.1 ms pulse plus 50 ms of cooling. Since the
next 10 Hz pulse would start at `0.1 s`, only one pulse is included.

## Geometry

The compact mesh spans:

- width: 1.2 mm
- scan length: 1.0 mm
- plate/gas height: 1.5 mm
- solid plate region: 0 to 1.2 mm in the height direction

The laser starts near the center of the compact scan track and moves 28.4 um
during the pulse, then remains at that final position during cooling.

## Run

```bash
cd /home/kanak/projects/solver_fix/ISW_CFD_CA_old/tutorials/connor_316L_single_pulse
sbatch job.sh
```

For a manual restart:

```bash
RESTART=1 sbatch job.sh
```
