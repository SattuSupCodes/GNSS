"""Calibration + orientation-engineering layer (Phase 2).

Submodules
----------
* gravity_estimation : low-frequency gravity / linear-acceleration separation.
* orientation_estimation : quaternion toolkit + complementary-filter attitude.
* phone_alignment : configurable device -> world (ENU) alignment.
* sensor_calibration : bias / scale / offset utilities + profiles.
* calibration_pipeline : end-to-end calibration of one canonical trip.

All modules preserve raw measurements; estimated / calibrated / aligned values
are produced in separate, clearly named columns.
"""