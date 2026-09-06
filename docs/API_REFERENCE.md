# Controller/Web API Reference

ทุก POST ด้าน motion ส่ง CommandEnvelope ผ่าน Controller IPC

## Demo

- `POST /api/demo/configure` — mode, slots, max_cycles, max_duration_s, dwell_s, speed_mm_s
- `POST /api/demo/validate`
- `POST /api/demo/arm` — คืน arm_token อายุ 30 วินาที
- `POST /api/demo/start` — ต้องส่ง arm_token
- `POST /api/demo/pause` — pause หลัง sample ปัจจุบัน
- `POST /api/demo/resume` — ตรวจ safety ใหม่
- `POST /api/demo/stop` — priority stop
- `GET /api/demo/status`
- `GET /api/demo/history`
- `GET /api/demo/export.csv`

## System control

- `POST /api/system/motion/disable`
- `POST /api/system/motion/enable`
- `POST /api/system/nucleo/reset-link`
- `GET /api/status`, `/health/live`, `/health/ready`

HTTP success ไม่หมายความว่าเครื่องเคลื่อนที่สำเร็จเสมอ ต้องตรวจ `accepted`, `state`, `reason`, `result` และ MachineSnapshot ล่าสุด

