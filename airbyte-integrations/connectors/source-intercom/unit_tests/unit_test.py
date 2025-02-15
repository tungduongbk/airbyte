#
# Copyright (c) 2021 Airbyte, Inc., all rights reserved.
#


import pytest
import requests
from airbyte_cdk.logger import AirbyteLogger
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams.http.auth import NoAuth
from source_intercom.source import (
    Admins,
    Companies,
    CompanyAttributes,
    CompanySegments,
    ContactAttributes,
    Contacts,
    ConversationParts,
    Conversations,
    IntercomStream,
    Segments,
    SourceIntercom,
    Tags,
    Teams,
)

logger = AirbyteLogger()


test_data = [
    (
        IntercomStream,
        {"data": [], "pages": {"next": "https://api.intercom.io/conversations?per_page=1&page=2"}},
        {"per_page": "1", "page": "2"},
    ),
    (
        Companies,
        {"data": [{"type": "company"}], "scroll_param": "25b649f7-4d33-4ef6-88f5-60e5b8244309"},
        {"scroll_param": "25b649f7-4d33-4ef6-88f5-60e5b8244309"},
    ),
    (
        Contacts,
        {
            "data": [],
            "pages": {
                "next": {"starting_after": "1HaSB+xrOyyMXAkS/c1RteCL7BzOzTvYjmjakgTergIH31eoe2v4/sbLsJWP" "\nIncfQLD3ouPkZlCwJ86F\n"}
            },
        },
        {"starting_after": "1HaSB+xrOyyMXAkS/c1RteCL7BzOzTvYjmjakgTergIH31eoe2v4/sbLsJWP\nIncfQLD3ouPkZlCwJ86F\n"},
    ),
]


@pytest.mark.parametrize(
    "intercom_class,response_json,expected_output_token", test_data, ids=["base pagination", "companies pagination", "contacts pagination"]
)
def test_get_next_page_token(intercom_class, response_json, expected_output_token, requests_mock):
    """
    Test shows that next_page parameters are parsed correctly from the response object and could be passed for next request API call,
    """

    requests_mock.get("https://api.intercom.io/conversations", json=response_json)
    response = requests.get("https://api.intercom.io/conversations")
    intercom_class = type("intercom_class", (intercom_class,), {"path": ""})
    test = intercom_class(authenticator=NoAuth).next_page_token(response)

    assert test == expected_output_token


def test_switch_to_standard_endpoint_if_scroll_expired(requests_mock):
    """
    Test shows that if scroll param expired we try sync with standard API.
    """

    url = "https://api.intercom.io/companies/scroll"
    requests_mock.get(
        url,
        json={"type": "company.list", "data": [{"type": "company", "id": "530370b477ad7120001d"}], "scroll_param": "expired_scroll_param"},
    )

    url = "https://api.intercom.io/companies/scroll?scroll_param=expired_scroll_param"
    requests_mock.get(url, json={"errors": [{"code": "not_found", "message": "scroll parameter not found"}]}, status_code=404)

    url = "https://api.intercom.io/companies"
    requests_mock.get(url, json={"type": "company.list", "data": [{"type": "company", "id": "530370b477ad7120001d"}]})

    stream1 = Companies(authenticator=NoAuth())

    records = []

    assert stream1._endpoint_type == Companies.EndpointType.scroll

    for slice in stream1.stream_slices(sync_mode=SyncMode.full_refresh):
        records += list(stream1.read_records(sync_mode=SyncMode, stream_slice=slice))

    assert stream1._endpoint_type == Companies.EndpointType.standard


def test_check_connection_ok(config, requests_mock):
    url = "https://api.intercom.io/tags"
    requests_mock.get(url, json={})
    ok, error_msg = SourceIntercom().check_connection(logger, config=config)

    assert ok
    assert not error_msg


def test_check_connection_empty_config(config):
    config = {}

    with pytest.raises(KeyError):
        SourceIntercom().check_connection(logger, config=config)


def test_check_connection_invalid_config(config):
    config.pop("start_date")
    ok, error_msg = SourceIntercom().check_connection(logger, config=config)

    assert not ok
    assert error_msg


def test_check_connection_exception(config):
    ok, error_msg = SourceIntercom().check_connection(logger, config=config)

    assert not ok
    assert error_msg


def test_streams(config):
    streams = SourceIntercom().streams(config)

    assert len(streams) == 11


@pytest.mark.parametrize(
    "stream, endpoint, response, expected",
    [
        (Admins, "/admins", {"type": "admin.list", "admins": [{"type": "admin", "id": "id"}]}, [{"id": "id", "type": "admin"}]),
        (
            Companies,
            "/companies/scroll",
            {"type": "company.list", "data": [{"type": "company", "id": "id"}]},
            [{"id": "id", "type": "company"}],
        ),
        (
            CompanySegments,
            "/companies/id/segments",
            {"type": "list", "data": [{"type": "segment", "id": "id"}]},
            [{"id": "id", "type": "segment"}],
        ),
        (Contacts, "/contacts", {"type": "list", "data": [{"type": "contact", "id": "id"}]}, [{"id": "id", "type": "contact"}]),
        (
            Conversations,
            "/conversations",
            {"type": "conversation.list", "conversations": [{"type": "conversation", "id": "id"}]},
            [{"id": "id", "type": "conversation"}],
        ),
        (
            ConversationParts,
            "/conversations/id",
            {"id": "id", "conversation_parts": {"conversation_parts": [{"type": "conversation_part", "id": "id"}]}},
            [{"conversation_id": "id", "id": "id", "type": "conversation_part"}],
        ),
        (
            CompanyAttributes,
            "/data_attributes",
            {"type": "list", "data": [{"type": "data_attribute", "id": "id"}]},
            [{"id": "id", "type": "data_attribute"}],
        ),
        (
            ContactAttributes,
            "/data_attributes",
            {"type": "list", "data": [{"type": "data_attribute", "id": "id"}]},
            [{"id": "id", "type": "data_attribute"}],
        ),
        (Segments, "/segments", {"type": "segment.list", "segments": [{"type": "segment", "id": "id"}]}, [{"id": "id", "type": "segment"}]),
        (Tags, "/tags", {"type": "list", "data": [{"type": "tag", "id": "id"}]}, [{"id": "id", "type": "tag"}]),
        (Teams, "/teams", {"teams": [{"type": "team", "id": "id"}]}, [{"id": "id", "type": "team"}]),
    ],
)
def test_read(stream, endpoint, response, expected, requests_mock):
    requests_mock.get("/conversations", json=response)
    requests_mock.get("/companies/scroll", json=response)
    requests_mock.get(endpoint, json=response)

    stream = stream(authenticator=NoAuth())

    records = []

    for slice in stream.stream_slices(sync_mode=SyncMode.full_refresh):
        records += list(stream.read_records(sync_mode=SyncMode, stream_slice=slice))

    assert records == expected


def build_conversations_response_body(conversations, next_url=None):
    return {"type": "conversation.list", "pages": {"next": next_url} if next_url else {}, "conversations": conversations}


def build_conversation_response_body(conversation_id, conversation_parts):
    return {
        "type": "conversation",
        "id": conversation_id,
        "conversation_parts": {
            "type": "conversation_part.list",
            "conversation_parts": conversation_parts,
            "total_count": len(conversation_parts),
        },
    }


@pytest.fixture
def single_conversation_response():
    return {
        "type": "conversation",
        "id": "151272900024304",
        "created_at": 1647365706,
        "updated_at": 1647366443,
        "conversation_parts": {
            "type": "conversation_part.list",
            "conversation_parts": [
                {"type": "conversation_part", "id": "13740311965"},
                {"type": "conversation_part", "id": "13740312024"},
            ],
            "total_count": 2,
        },
    }


@pytest.fixture
def conversation_parts_responses():
    return [
        (
            "https://api.intercom.io/conversations",
            build_conversations_response_body(
                conversations=[{"id": "151272900026677", "updated_at": 1650988600}, {"id": "151272900026666", "updated_at": 1650988500}],
                next_url="https://api.intercom.io/conversations?per_page=2&page=2",
            ),
        ),
        (
            "https://api.intercom.io/conversations?per_page=2&page=2",
            build_conversations_response_body(
                conversations=[
                    {"id": "151272900026466", "updated_at": 1650988450},
                    {"id": "151272900026680", "updated_at": 1650988100},  # Older than state, won't be processed
                ]
            ),
        ),
        (
            "https://api.intercom.io/conversations/151272900026677",
            build_conversation_response_body(
                conversation_id="151272900026677",
                conversation_parts=[{"id": "13740311961", "updated_at": 1650988300}, {"id": "13740311962", "updated_at": 1650988450}],
            ),
        ),
        (
            "https://api.intercom.io/conversations/151272900026666",
            build_conversation_response_body(
                conversation_id="151272900026666",
                conversation_parts=[{"id": "13740311955", "updated_at": 1650988150}, {"id": "13740312056", "updated_at": 1650988500}],
            ),
        ),
        (
            "https://api.intercom.io/conversations/151272900026466",
            build_conversation_response_body(
                conversation_id="151272900026466", conversation_parts=[{"id": "13740311970", "updated_at": 1650988600}]
            ),
        ),
    ]


def test_conversation_part_has_conversation_id(requests_mock, single_conversation_response):
    """
    Test shows that conversation_part records include the `conversation_id` field.
    """
    conversation_id = single_conversation_response["id"]
    url = f"https://api.intercom.io/conversations/{conversation_id}"
    requests_mock.get(url, json=single_conversation_response)

    conversation_parts = ConversationParts(authenticator=NoAuth())

    record_count = 0
    for record in conversation_parts.read_records(sync_mode=SyncMode.incremental, stream_slice={"id": conversation_id}):
        assert record["conversation_id"] == "151272900024304"
        record_count += 1

    assert record_count == 2


def test_conversation_part_filtering_based_on_conversation(requests_mock, conversation_parts_responses):
    """
    Test shows that conversation_parts filters conversations (from parent stream) correctly
    """
    updated_at = 1650988200
    state = {"updated_at": updated_at}
    expected_record_ids = set()
    for response_tuple in conversation_parts_responses:
        requests_mock.register_uri("GET", response_tuple[0], json=response_tuple[1])
        if "conversation_parts" in response_tuple[1]:
            expected_record_ids.update([cp["id"] for cp in response_tuple[1]["conversation_parts"]["conversation_parts"]])

    records = []
    conversation_parts = ConversationParts(authenticator=NoAuth())
    for slice in conversation_parts.stream_slices(sync_mode=SyncMode.incremental, stream_state=state):
        records.extend(list(conversation_parts.read_records(sync_mode=SyncMode.incremental, stream_slice=slice, stream_state=state)))

    assert expected_record_ids == {r["id"] for r in records}
