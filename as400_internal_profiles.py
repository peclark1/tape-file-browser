"""Identity-only view of archived 0E/C4 INTPRF primaries.

Never opens either internal-profile or user-profile body bytes. Matching
by name is useful evidence, not a validated object pointer, credential
equivalence, active signon ability or a proven ownership relationship.
"""
from as400_capabilities import object_row, section


class InternalProfileExplorer:
    """Match recovered INTPRF identities to recovered USRPRF identities safely."""

    def __init__(self, inventory):
        self.inventory = inventory
        self._users_by_name = {}
        for target in inventory.objects:
            if target.type_code == "08/01" and target.name:
                self._users_by_name.setdefault(target.name.upper(), []).append(target)
        for matches in self._users_by_name.values():
            matches.sort(key=lambda o: (o.library_name or "",
                                        o.segment.start_lba))

    def rows(self, obj):
        if obj.type_code != "0E/C4":
            raise ValueError("Not an internal-profile identity")
        if not obj.name:
            return [section("Identity unavailable", [
                "No printable identity recovered for this INTPRF primary.",
                "No profile body or credential data inspected."])]
        name = obj.name.upper()
        matches = self._users_by_name.get(name, [])
        rows = [section("Internal-profile identity", [
            f"Recovered INTPRF {obj.library_name or '<unassigned>'}/{obj.name}",
            f"Primary LBA {obj.segment.start_lba}; MI 0E/C4",
            f"{len(matches)} exact-name USRPRF primary candidate(s) recovered.",
            "Name equality is an empirical association, not a decoded pointer.",
            "Names can be stale, incomplete or duplicated across recovered primaries.",
            "Only EPA object identity metadata is used; neither profile's contents, "
            "passwords, authorization fields, nor credential payloads are read.",
            "A missing user-profile primary does NOT prove no historical profile existed."])]
        for target in matches:
            rows.append(object_row(target, "Exact recovered name only; use 5 for existing safe profile identity view"))
        if not matches:
            rows.append(section("No name match", [
                "No recovered USRPRF primary has this exact name.",
                "This is not evidence that the internal profile was invalid or inactive."]))
        return rows
