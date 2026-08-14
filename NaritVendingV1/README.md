# NaritVendingV1

Deployment profile for the IRIV Pi and IRIV IO machine.

- HMI name: `V1`
- Web: `http://iriv.local/`
- SSH host: `pi@iriv.local`
- Remote application: `/home/admin/NaritVendingV1`
- Machine config source: `../machine_config.iriv.json`
- Hardware config source: `../hardware_config.iriv.json`

The Python application remains in the shared `narit_vending/` source folder.
IRIV-specific configuration, deployment path, and system services are isolated
from the MOCKUP profile.

Deploy from the repository root:

```powershell
.\NaritVendingV1\deploy.ps1
```
