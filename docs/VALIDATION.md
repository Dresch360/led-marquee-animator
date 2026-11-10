# Validation and remaining checks

## Physical observations from the personal setup

- The Windows uploader sent individual GIFs that played on the 96 × 16 sign.
- The Pi 3 discovered the sign and sent text and GIFs that played correctly.
- The user confirmed the original Pi page and playback worked and later reported that the shuffle update worked.
- Full combined reels did not produce acceptable playback. A 64-frame diagnostic also failed to display correctly despite a sender success message.

This repository import changes organization and documentation, not application behavior. It does not modify the installed PC or Pi applications.

## Automated coverage

The Pi suite contains 25 tests covering GIF fit and frame preservation, including identical frames; playlist validation; ordered and shuffled rounds; no immediate boundary repeats; retrying the same pending item; the interval starting after upload completion; stopping and cancellation; saved running/stopped state; file validation and upload protection; CSRF tokens; child-process exit and success-marker handling; and the upload watchdog.

These tests simulate the driver and Bluetooth results. They cannot prove physical playback or controller capacity.

Prior development also exercised the web controls against a local Waitress server using a DOM environment, including saving, uploads, shuffle and start/stop. This was not a complete native-browser rendering test. The user separately viewed the page on their own network.

## Before claiming general compatibility

- Test a clean Windows installation and a clean Pi installation using the documented release flow.
- Watch a complete shuffled round on the sign, including the round boundary.
- Verify playback continues with the browser closed.
- Verify display power-off waiting and recovery after power-on.
- Verify Pi reboot, Bluetooth availability and saved running/stopped behavior.
- Check the actual frame and payload limits for each claimed controller variant.
- Check power stability on the target Pi. The prototype recorded historical undervoltage/throttling; its resolution was not established.

A success log means the sender completed its checks. Always inspect the physical panel when validating a new controller, upload mode or frame limit.
