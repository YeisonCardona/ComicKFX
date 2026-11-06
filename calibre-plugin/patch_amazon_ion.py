from pathlib import Path

# Locate the amazon-ion source file inside the build directory.
source = Path("./lib/amazon/ion/writer_binary_raw_fields.py")

# Read the original source code.
content = source.read_text()

# Define the exact code block to replace.
old = """\
            assert _write_int_uncached(self._cached_ints, signed_value) == 1
            assert _write_varint_uncached(self._cached_varints, signed_value) == 1
            assert _write_uint_uncached(self._cached_uints, cached_value) == 1
            assert _write_varuint_uncached(self._cached_varuints, cached_value) == 1
"""

# Define the corrected implementation.
new = """\
            if _write_int_uncached(self._cached_ints, signed_value) != 1:
                raise AssertionError("Invalid cached int")
            if _write_varint_uncached(self._cached_varints, signed_value) != 1:
                raise AssertionError("Invalid cached varint")
            if _write_uint_uncached(self._cached_uints, cached_value) != 1:
                raise AssertionError("Invalid cached uint")
            if _write_varuint_uncached(self._cached_varuints, cached_value) != 1:
                raise AssertionError("Invalid cached varuint")
"""

# Ensure the expected source code exists exactly once.
matches = content.count(old)

if matches != 1:
    raise RuntimeError(
        f"Expected exactly one matching block, found {matches}. "
        "The amazon-ion source may have changed."
    )

# Apply the patch.
source.write_text(content.replace(old, new, 1))

print(f"Patch applied successfully: {source}")
