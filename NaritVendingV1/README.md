# NaritVendingV1

Deployment profile for the IRIV Pi and IRIV IO machine.

- HMI name: `V1`
- Web: `http://iriv.local/`
- SSH host: `pi@iriv.local`
- Remote application: `/home/admin/NaritVendingV1`
- Machine config: `machine_config.iriv.json`
- Hardware config: `hardware_config.iriv.json`
- Application source: `narit_vending/`
- Tests: `tests/`

`machine_config.json` and `hardware_config.json` are local generic-GPIO test
fixtures inherited by the shared test suite. V1 runtime and deployment
explicitly use the authoritative `*.iriv.json` files.

This folder contains its own deployable copy of the Python application. Run
`..\scripts\sync_profile_code.ps1` from the repository root when a shared fix
must be copied into both independent profiles.

Deploy from the repository root:

```powershell
.\NaritVendingV1\deploy.ps1
```
