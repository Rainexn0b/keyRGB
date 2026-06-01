# Brightness logging

```bash
KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb >> ./keyrgb-brightness.log 2>&1


```

# Runtime debug

```bash
KEYRGB_DEBUG=1 ./keyrgb
KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb
KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb
```

`KEYRGB_DEBUG_BRIGHTNESS=1` now also emits lighting start-policy events and richer hardware recovery events, including whether a deck restore used an in-place transition or a full effect restart.

If you also want raw reactive input keypress traces, enable them separately with `KEYRGB_DEBUG_REACTIVE_INPUT=1`.
