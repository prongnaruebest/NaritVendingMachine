# NaritVendingMOCKUP

Deployment profile for the original Raspberry Pi mockup.

- HMI name: `MOCKUP`
- Web: `http://naritvendingmachine/`
- SSH host: `narit-pi`
- Remote application: `/home/admin/NaritVendingMOCKUP`
- Machine config: `machine_config.json`
- Hardware config: `hardware_config.json`
- Application source: `narit_vending/`
- Tests: `tests/`

This folder contains its own deployable copy of the Python application. Run
`..\scripts\sync_profile_code.ps1` from the repository root when a shared fix
must be copied into both independent profiles.

Deploy from the repository root:

```powershell
.\NaritVendingMOCKUP\deploy.ps1
```
