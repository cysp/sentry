from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sentry_protos.snuba.v1.trace_item_attribute_pb2 import (
    AttributeAggregation,
    AttributeKey,
    VirtualColumnContext,
)

from sentry.exceptions import InvalidSearchQuery
from sentry.search.eap import constants
from sentry.search.events.types import SnubaParams
from sentry.utils.validators import is_event_id, is_span_id


@dataclass(frozen=True)
class ResolvedColumn:
    # The alias for this column
    public_alias: str  # `p95() as foo` has the public alias `foo` and `p95()` has the public alias `p95()`
    # The internal rpc alias for this column
    internal_name: str
    # The public type for this column
    search_type: str
    # The internal rpc type for this column, optional as it can mostly be inferred from search_type
    internal_type: AttributeKey.Type.ValueType | None = None
    # Processor is the function run in the post process step to transform a row into the final result
    processor: Callable[[Any], Any] | None = None
    # Validator to check if the value in a query is correct
    validator: Callable[[Any], bool] | None = None

    def process_column(row: Any) -> None:
        """Pull the column from row, then process it and mutate it"""
        raise NotImplementedError()

    def validate(self, value: Any) -> None:
        if self.validator is not None:
            if not self.validator(value):
                raise InvalidSearchQuery(f"{value} is an invalid value for {self.public_alias}")

    @property
    def proto_definition(self) -> AttributeAggregation | AttributeKey:
        """The definition of this function as needed by the RPC"""
        # Placeholder to implement search for now
        return AttributeKey(
            name=self.internal_name,
            type=self.internal_type
            if self.internal_type is not None
            else constants.TYPE_MAP[self.search_type],
        )


SPAN_COLUMN_DEFINITIONS = {
    column.public_alias: column
    for column in [
        ResolvedColumn(
            public_alias="id",
            internal_name="span_id",
            search_type="string",
            validator=is_span_id,
        ),
        ResolvedColumn(
            public_alias="organization.id", internal_name="organization_id", search_type="string"
        ),
        ResolvedColumn(
            public_alias="span.action",
            internal_name="action",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="span.description",
            internal_name="name",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="description",
            internal_name="name",
            search_type="string",
        ),
        # Message maps to description, this is to allow wildcard searching
        ResolvedColumn(
            public_alias="message",
            internal_name="name",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="span.domain", internal_name="attr_str[domain]", search_type="string"
        ),
        ResolvedColumn(
            public_alias="span.group", internal_name="attr_str[group]", search_type="string"
        ),
        ResolvedColumn(public_alias="span.op", internal_name="attr_str[op]", search_type="string"),
        ResolvedColumn(
            public_alias="span.category", internal_name="attr_str[category]", search_type="string"
        ),
        ResolvedColumn(
            public_alias="span.self_time", internal_name="exclusive_time_ms", search_type="duration"
        ),
        ResolvedColumn(
            public_alias="span.status", internal_name="attr_str[status]", search_type="string"
        ),
        ResolvedColumn(
            public_alias="trace",
            internal_name="trace_id",
            search_type="string",
            validator=is_event_id,
        ),
        ResolvedColumn(
            public_alias="messaging.destination.name",
            internal_name="attr_str[messaging.destination.name]",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="messaging.message.id",
            internal_name="attr_str[messaging.message.id]",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="span.status_code",
            internal_name="attr_str[status_code]",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="replay.id", internal_name="attr_str[replay_id]", search_type="string"
        ),
        ResolvedColumn(
            public_alias="span.ai.pipeline.group",
            internal_name="attr_str[ai_pipeline_group]",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="trace.status",
            internal_name="attr_str[trace.status]",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="browser.name",
            internal_name="attr_str[browser.name]",
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="ai.total_cost",
            internal_name="attr_num[ai.total_cost]",
            search_type="number",
        ),
        ResolvedColumn(
            public_alias="ai.total_tokens.used",
            internal_name="attr_num[ai_total_tokens_used]",
            search_type="number",
        ),
        ResolvedColumn(
            public_alias="project",
            internal_name="project_id",
            internal_type=constants.INT,
            search_type="string",
        ),
        ResolvedColumn(
            public_alias="project.slug",
            internal_name="project_id",
            search_type="string",
            internal_type=constants.INT,
        ),
    ]
}


def project_context_constructor(column_name: str) -> Callable[[SnubaParams], VirtualColumnContext]:
    def context_constructor(params: SnubaParams) -> VirtualColumnContext:
        return VirtualColumnContext(
            from_column_name="project_id",
            to_column_name=column_name,
            value_map={
                str(project_id): project_name
                for project_id, project_name in params.project_id_map.items()
            },
        )

    return context_constructor


VIRTUAL_CONTEXTS = {
    "project": project_context_constructor("project"),
    "project.slug": project_context_constructor("project.slug"),
}


Processors: dict[str, Callable[[Any], Any]] = {}