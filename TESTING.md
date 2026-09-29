# TechBiz v2.3 Test Summary

This build was tested before packaging.

- Logo resize/validation suite: 52/52 passed.
  - Wide, square and portrait logos
  - Transparent PNG and WEBP
  - JPEG and GIF normalization
  - Aspect-ratio preservation
  - Maximum 512px longest edge
  - Invalid image rejection
- Core business regression suite: 48/48 passed.
  - Authentication, customers, inventory, sales, payments
  - Stock deduction and oversell protection
  - Suppliers, purchases, stock increases
  - Printing jobs, expenses, cashbook, reports, CSV export
  - Business settings and password change
- Real localhost HTTP smoke test passed.
