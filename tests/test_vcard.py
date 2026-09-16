from garmin_sleep_score_notification.vcard import build_vcard

PHOTO = b"\x89PNG\r\n\x1a\n" + b"x" * 200


def test_vcard_has_required_fields():
    vcf = build_vcard("Garmin Sleep", "sleep@westwallaby.co.uk", PHOTO).decode()
    assert vcf.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n")
    assert vcf.endswith("END:VCARD\r\n")
    assert "FN:Garmin Sleep" in vcf
    assert "N:;Garmin Sleep;;;" in vcf
    assert "EMAIL;TYPE=INTERNET:sleep@westwallaby.co.uk" in vcf


def test_long_photo_line_is_folded_per_rfc2426():
    vcf = build_vcard("Garmin Sleep", "sleep@westwallaby.co.uk", PHOTO).decode()
    lines = vcf.split("\r\n")
    assert all(len(line) <= 75 for line in lines)
    photo_start = next(i for i, line in enumerate(lines) if line.startswith("PHOTO"))
    assert lines[photo_start + 1].startswith(" ")


def test_photo_roundtrips_as_base64():
    import base64

    vcf = build_vcard("Garmin Sleep", "sleep@westwallaby.co.uk", PHOTO).decode()
    unfolded = vcf.replace("\r\n ", "")
    b64 = next(
        line for line in unfolded.split("\r\n") if line.startswith("PHOTO")
    ).split(":", 1)[1]
    assert base64.b64decode(b64) == PHOTO
