---
content_hash: sha256:4d9a3cd97faae4e6669c07f6bc51e54b50049ff3b544a1fda863614e79e0891f
generation_id: 1
generator: ecommerce@1.0.0
layer: ops
skill: ecommerce
tags:
  - capabilities
type: summary
updated: "2026-04-08T05:22:36.796Z"
version: 1
---
# E-commerce Capabilities

## Commands
- `ecom watch add <name> --url <url> [--target <price>]`
- `ecom watch list`
- `ecom watch remove <id>`
- `ecom price history <id>`
- `ecom price update <id> <price>`
- `ecom order add <name> [--tracking <num>]`
- `ecom order list [--status <status>]`
- `ecom order update <id> [--status <s>] [--tracking <n>]`
- `ecom margin --cost <c> --sell <s> [--fees <pct>]`
- `ecom alert list [--pending]`
- `ecom alert ack <id>`
- `ecom refresh`
