<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Contribution guide
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# Contributing

Keep this bridge outside laser control authority: it must never arm, fire or
override a laser controller. New observations and adapters must fail closed and
must not bypass the shared SDK job gate or independent laser safety.

Before opening a change, run `build-test.bat` on Windows or `bash build-test.sh`
on Linux. Add a focused test for every interlock or admission rule changed.
Hardware behavior must identify its tested interface and safe failure mode;
unverified laser support is not ready support.
