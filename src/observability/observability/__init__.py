"""Observability service: campaign timeline + service health dashboard.

Reads the ``trace_events`` Mongo collection populated by every other service's
:class:`TracedBroker` (and by ``trace_operation`` for non-broker flows), groups
events by ``campaign_id``, and renders both JSON (for engineers / scripts) and
HTML (for product / ops) views of a campaign's pipeline progress.
"""
