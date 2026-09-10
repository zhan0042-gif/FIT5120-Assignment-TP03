"""Official Victorian address autocomplete endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_address_client
from app.providers.interfaces import AddressClient
from app.schemas.households import AddressSuggestion, CoordinateLookupRequest
from app.services.context import AddressSuggestionService


router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/suggestions", response_model=list[AddressSuggestion])
def list_address_suggestions(
    q: Annotated[str, Query(min_length=1, max_length=120)],
    address_client: Annotated[AddressClient, Depends(get_address_client)],
) -> list[AddressSuggestion]:
    """Return provider-backed Victorian candidates; selection is not verification."""
    return AddressSuggestionService(address_client).suggest(q.strip())


@router.post("/nearby-addresses", response_model=list[AddressSuggestion])
def list_nearby_addresses(
    request: CoordinateLookupRequest,
    address_client: Annotated[AddressClient, Depends(get_address_client)],
) -> list[AddressSuggestion]:
    """Return nearby Victorian candidates; user confirmation is still required."""
    return AddressSuggestionService(address_client).reverse(
        request.latitude, request.longitude
    )
