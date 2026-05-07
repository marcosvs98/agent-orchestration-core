OUTBOUND_AUTHORIZATION_SECRET_REF_KEY = "outbound_authorization_secret_ref"


def outbound_authorization_secret_ref_from_server_metadata(meta: object) -> str | None:
    if not isinstance(meta, dict):
        return None
    raw = meta.get(OUTBOUND_AUTHORIZATION_SECRET_REF_KEY)
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None
