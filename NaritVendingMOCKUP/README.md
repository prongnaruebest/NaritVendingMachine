# NaritVendingMOCKUP

Deployment profile for the original Raspberry Pi mockup.

- HMI name: `MOCKUP`
- Web: `http://naritvendingmachine/`
- SSH host: `narit-pi`
- Remote application: `/home/admin/NaritVendingMOCKUP`
- Machine config source: `../machine_config.json`
- Hardware config source: `../hardware_config.json`

The Python application remains in the shared `narit_vending/` source folder.
This prevents fixes from diverging between MOCKUP and V1 while configuration,
deployment path, and system services remain independent.

Deploy from the repository root:

```powershell
.\NaritVendingMOCKUP\deploy.ps1
```
