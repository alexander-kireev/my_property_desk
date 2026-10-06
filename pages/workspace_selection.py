"""Keep a selected workspace record and its paginated list in sync."""


def page_for_record(queryset, record_id, page_size):
    for index, pk in enumerate(queryset.values_list("pk", flat=True).iterator(chunk_size=200)):
        if pk == record_id:
            return index // page_size + 1
    return None


def amended_query_url(request, *, remove=(), changes=None):
    parameters = request.GET.copy()
    for name in remove:
        parameters.pop(name, None)
    for name, value in (changes or {}).items():
        if value is None:
            parameters.pop(name, None)
        else:
            parameters[name] = str(value)
    query = parameters.urlencode()
    return f"{request.path}?{query}" if query else request.path


def resolve_selection(request, *, filtered, owned, page_size):
    """Return (record, natural_page, outside_filters, redirect_url)."""
    raw = request.GET.get("selected")
    if raw is None:
        return None, None, False, None
    try:
        record_id = int(raw)
    except TypeError, ValueError:
        record_id = 0
    record = owned.filter(pk=record_id).first() if record_id > 0 else None
    if record is None:
        return None, None, False, amended_query_url(request, remove=("selected", "open"))
    natural_page = page_for_record(filtered, record_id, page_size)
    if natural_page is not None:
        wanted = str(natural_page) if natural_page > 1 else ""
        current = request.GET.get("page", "")
        if current != wanted:
            return (
                record,
                natural_page,
                False,
                amended_query_url(
                    request, changes={"page": natural_page if natural_page > 1 else None}
                ),
            )
    return record, natural_page, natural_page is None, None
