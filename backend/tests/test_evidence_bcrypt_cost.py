"""AC-15 evidence: passwords are hashed with bcrypt at cost >= 10 (the app uses cost 12)."""
from app.auth import hash_password, verify_password


def _cost(h: str) -> int:
    # bcrypt format: $2b$<cost>$<22 char salt><31 char hash>
    parts = h.split("$")
    assert parts[1] in ("2a", "2b", "2y"), f"not a bcrypt hash: {h[:7]}"
    return int(parts[2])


def test_new_password_hash_uses_bcrypt_cost_at_least_10():
    h = hash_password("Passw0rd!x")
    print(f"hash prefix: {h[:7]}  cost={_cost(h)}")
    assert _cost(h) >= 10
    assert verify_password("Passw0rd!x", h)
    assert not verify_password("wrong-password", h)


def test_hashes_are_salted():
    assert hash_password("Passw0rd!x") != hash_password("Passw0rd!x")
