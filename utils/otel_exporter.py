"""OpenTelemetry custom exporter and span processor for LangSmith tracing.

This module provides custom OpenTelemetry components for:
- Modifying span attributes before export
- Filtering spans based on regex patterns
- Restructuring traces by reparenting spans when parents are filtered
"""

import os
import re
import logging
from typing import Sequence, Dict, Optional

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, SpanProcessor

logger = logging.getLogger(__name__)


class TraceModifyingSpanProcessor(SpanProcessor):
    """Custom span processor that modifies spans when they end (before export).
    
    This processor is called when a span ends, allowing you to modify
    span attributes before they are batched and exported.
    
    You can:
    - Add/modify/remove span attributes
    - Filter spans (by not adding them to the processor)
    - Add computed metadata based on span properties
    """
    
    def on_end(self, span: ReadableSpan):
        """Called when a span ends. Modify the span here before it's exported."""
        logger.debug(f"TraceModifyingSpanProcessor.on_end() called for span: {span.name}")
        
        # ============================================================
        # CUSTOMIZE TRACE MODIFICATIONS HERE
        # ============================================================
        # Note: ReadableSpan allows attribute modification via _attributes dict
        # or by accessing the underlying span if it's still mutable
        
        # Example: Add environment information
        span._attributes["deployment.environment"] = os.getenv("ENVIRONMENT", "development")
        
        # Example: Add service version
        span._attributes["service.version"] = os.getenv("SERVICE_VERSION", "1.0.0")
        
        # Example: Add custom processor marker
        span._attributes["custom.processor"] = "trace_modifier"
        
        # Example: Modify span attributes based on conditions
        if span.name.startswith("google_adk"):
            span._attributes["agent.type"] = "google_adk"
        
        # Example: Add computed attributes
        if hasattr(span, 'end_time') and hasattr(span, 'start_time') and span.end_time and span.start_time:
            duration_ns = span.end_time - span.start_time
            span._attributes["duration_ms"] = duration_ns / 1_000_000
        
        # Example: Filter spans (mark for filtering - actual filtering happens in exporter)
        # span._attributes["_filter"] = True
        
        # Example: Sanitize sensitive data
        # if "api_key" in span._attributes:
        #     span._attributes["api_key"] = "***REDACTED***"
        
        # ============================================================
        # End of customization section
        # ============================================================
    
    def shutdown(self):
        """Shutdown the processor."""
        pass
    
    def force_flush(self, timeout_millis: int = 30000):
        """Force flush the processor."""
        pass


def should_filter_span(span: ReadableSpan, filter_patterns: list[re.Pattern]) -> bool:
    """Check if a span should be filtered out based on regex patterns.
    
    Args:
        span: The span to check
        filter_patterns: List of compiled regex patterns to match against span names
        
    Returns:
        True if the span should be filtered out (not exported), False otherwise
    """
    if not filter_patterns:
        return False
    
    span_name = span.name
    for pattern in filter_patterns:
        if pattern.search(span_name):
            logger.debug(f"Filtering out span '{span_name}' (matched pattern: {pattern.pattern})")
            return True
    
    return False


def restructure_trace_spans(
    all_spans: Sequence[ReadableSpan],
    kept_spans: Sequence[ReadableSpan],
    filtered_span_ids: set[int]
) -> Sequence[ReadableSpan]:
    """Restructure trace by reparenting spans whose parents were filtered.
    
    This function implements trace restructuring/span reparenting. When a parent span
    is filtered out, its children are reparented to the filtered span's parent (or
    nearest non-filtered ancestor).
    
    Args:
        all_spans: All spans (including filtered ones) - needed to build complete parent map
        kept_spans: Spans that will be exported (non-filtered)
        filtered_span_ids: Set of span IDs that were filtered out
        
    Returns:
        Sequence of restructured spans with updated parent contexts
    """
    if not filtered_span_ids:
        return kept_spans
    
    # Build maps for efficient lookup
    # span_by_id: all spans (for parent chain traversal)
    # kept_span_by_id: only kept spans (for reparenting)
    span_by_id: Dict[int, ReadableSpan] = {}
    kept_span_by_id: Dict[int, ReadableSpan] = {}
    parent_map: Dict[int, int] = {}  # child_span_id -> parent_span_id
    
    # Build complete parent map from ALL spans (including filtered) for chain traversal
    for span in all_spans:
        span_id = span.context.span_id
        span_by_id[span_id] = span
        
        # Get parent span ID from span context
        parent_context = span.parent
        if parent_context and parent_context.span_id:
            parent_map[span_id] = parent_context.span_id
    
    # Build map of kept spans only (for reparenting)
    for span in kept_spans:
        kept_span_by_id[span.context.span_id] = span
    
    # Find the nearest non-filtered ancestor for each span
    def find_nearest_non_filtered_ancestor(span_id: int) -> Optional[int]:
        """Find the nearest ancestor that wasn't filtered and exists in kept spans."""
        visited = set()
        current_id = parent_map.get(span_id)
        
        while current_id and current_id not in visited:
            visited.add(current_id)
            # Check if this ancestor is not filtered AND exists in kept spans
            if current_id not in filtered_span_ids and current_id in kept_span_by_id:
                return current_id
            current_id = parent_map.get(current_id)
        
        return None
    
    # Now restructure only the kept spans
    # We need to process spans in multiple passes to handle nested reparenting
    restructured_spans = list(kept_spans)
    reparented_count = 0
    max_iterations = 10  # Prevent infinite loops
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        spans_modified_this_iteration = 0
        
        for span in restructured_spans:
            span_id = span.context.span_id
            
            # Get current parent from the span itself (may have been updated in previous iteration)
            current_parent_context = span.parent
            current_parent_id = current_parent_context.span_id if current_parent_context else None
            
            # Also check the original parent from parent_map
            original_parent_id = parent_map.get(span_id)
            
            # Use current parent if available, otherwise use original
            # If current parent is not filtered, we don't need to reparent
            parent_id = current_parent_id or original_parent_id
            
            # Only reparent if the parent is filtered
            if parent_id and parent_id in filtered_span_ids:
                logger.debug(
                    f"[Iteration {iteration}] Span '{span.name}' (span_id={span_id:x}) has filtered parent "
                    f"(span_id={parent_id:x}), finding new parent..."
                )
                # Find nearest non-filtered ancestor
                new_parent_id = find_nearest_non_filtered_ancestor(span_id)
                
                if new_parent_id:
                    logger.debug(f"Found new parent for '{span.name}': span_id={new_parent_id:x}")
                    # Reparent this span - use kept_span_by_id to ensure it's a kept span
                    new_parent_span = kept_span_by_id.get(new_parent_id)
                    if new_parent_span:
                        logger.debug(
                            f"Attempting to reparent '{span.name}' to '{new_parent_span.name}' "
                            f"(span_id={new_parent_id:x})"
                        )
                    else:
                        logger.warning(
                            f"Found parent span_id={new_parent_id:x} for '{span.name}' but it's not in kept spans. "
                            f"This shouldn't happen - the ancestor finder should only return kept spans."
                        )
                        continue  # Skip reparenting for this span
                    # Try to modify the parent through internal SDK structures
                    # ReadableSpan wraps a Span object - try to access and modify it
                    reparented = False
                    
                    # Method 1: Try accessing _parent attribute directly (most common)
                    if hasattr(span, '_parent'):
                        try:
                            old_parent = span._parent
                            span._parent = new_parent_span.context
                            reparented = True
                            logger.info(
                                f"✓ Reparented '{span.name}' via _parent: "
                                f"old_parent={old_parent.span_id:x if old_parent else None}, "
                                f"new_parent={new_parent_span.context.span_id:x}"
                            )
                        except (AttributeError, TypeError, ValueError) as e:
                            logger.debug(f"Could not modify _parent: {e}")
                    
                    # Method 2: Try accessing underlying span object (_span or _readable_span)
                    if not reparented:
                        for attr_name in ['_span', '_readable_span', 'span']:
                            if hasattr(span, attr_name):
                                try:
                                    underlying_span = getattr(span, attr_name)
                                    if hasattr(underlying_span, 'parent'):
                                        underlying_span.parent = new_parent_span.context
                                        reparented = True
                                        logger.debug(f"Successfully reparented via {attr_name}.parent")
                                        break
                                    elif hasattr(underlying_span, '_parent'):
                                        underlying_span._parent = new_parent_span.context
                                        reparented = True
                                        logger.debug(f"Successfully reparented via {attr_name}._parent")
                                        break
                                except (AttributeError, TypeError, ValueError) as e:
                                    logger.debug(f"Could not modify {attr_name}: {e}")
                                    continue
                    
                    if reparented:
                        reparented_count += 1
                        spans_modified_this_iteration += 1
                        # Verify the reparenting worked
                        current_parent = span.parent
                        if current_parent and current_parent.span_id == new_parent_span.context.span_id:
                            logger.info(
                                f"✓ Successfully reparented '{span.name}' (span_id={span_id:x}) "
                                f"to '{new_parent_span.name}' (span_id={new_parent_id:x})"
                            )
                            # Update parent_map for this span so children can find it
                            parent_map[span_id] = new_parent_id
                        else:
                            logger.warning(
                                f"⚠ Reparenting attempt for '{span.name}' may have failed. "
                                f"Current parent span_id: {current_parent.span_id:x if current_parent else None}, "
                                f"Expected: {new_parent_id:x}"
                            )
                    else:
                        # Fallback: Use span links to indicate the new parent relationship
                        # This helps LangSmith understand the restructured trace
                        try:
                            # Add a link to the new parent span
                            from opentelemetry.trace import Link
                            from opentelemetry.trace.span import TraceState
                            
                            # Try to add link through internal structure
                            if hasattr(span, '_links'):
                                link = Link(new_parent_span.context)
                                if isinstance(span._links, list):
                                    span._links.append(link)
                                reparented_count += 1
                                spans_modified_this_iteration += 1
                                parent_map[span_id] = new_parent_id  # Update parent_map
                                logger.debug(
                                    f"Added link to new parent for span '{span.name}' "
                                    f"(span_id={span_id:x}) -> parent '{new_parent_span.name}' "
                                    f"(span_id={new_parent_id:x})"
                                )
                            else:
                                # Last resort: add metadata attributes
                                span._attributes["_reparented_from"] = f"span_id:{parent_id:x}"
                                span._attributes["_reparented_to"] = f"span_id:{new_parent_id:x}"
                                span._attributes["_reparented_to_name"] = new_parent_span.name
                                reparented_count += 1
                                spans_modified_this_iteration += 1
                                parent_map[span_id] = new_parent_id  # Update parent_map
                                logger.debug(
                                    f"Marked span '{span.name}' for reparenting via attributes "
                                    f"(from span_id={parent_id:x} to span_id={new_parent_id:x})"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Could not reparent span '{span.name}': {e}. "
                                f"Span may appear orphaned in LangSmith."
                            )
        
        # If no spans were modified this iteration, we're done
        if spans_modified_this_iteration == 0:
            logger.debug(f"No more spans to reparent after {iteration} iteration(s)")
            break
    
    if reparented_count > 0:
        logger.info(f"Reparented {reparented_count} span(s) after filtering in {iteration} iteration(s)")
    else:
        logger.warning(
            "⚠ No spans were successfully reparented. "
            "Child spans may appear orphaned in LangSmith. "
            "This may be because ReadableSpan parent context is immutable."
        )
    
    # Log final span structure for debugging
    logger.info("Final span structure after restructuring:")
    for span in restructured_spans:
        parent_context = span.parent
        if parent_context:
            parent_span = span_by_id.get(parent_context.span_id)
            parent_name = parent_span.name if parent_span else f"span_id={parent_context.span_id:x}"
            logger.info(f"  - {span.name} → parent: {parent_name}")
        else:
            logger.info(f"  - {span.name} → root")
    
    return restructured_spans


class ModifyingSpanExporter(SpanExporter):
    """Wrapper exporter that can filter or log spans right before export.
    
    Note: Attribute modification should be done in SpanProcessor.on_end()
    This exporter is mainly for filtering or logging.
    """
    
    def __init__(self, base_exporter: SpanExporter, filter_patterns: list[str] = None):
        """Initialize with a base exporter to wrap.
        
        Args:
            base_exporter: The base exporter to wrap
            filter_patterns: List of regex pattern strings to filter spans by name
        """
        self.base_exporter = base_exporter
        self.filter_patterns = self._compile_filter_patterns(filter_patterns or [])
        # Reparenting is controlled by environment variable (checked in export method)
    
    @staticmethod
    def _compile_filter_patterns(pattern_strings: list[str]) -> list[re.Pattern]:
        """Compile regex patterns from string list.
        
        Args:
            pattern_strings: List of regex pattern strings
            
        Returns:
            List of compiled regex patterns
        """
        patterns = []
        for pattern_str in pattern_strings:
            try:
                pattern = re.compile(pattern_str)
                patterns.append(pattern)
                logger.debug(f"Compiled filter pattern: {pattern_str}")
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern_str}': {e}. Skipping.")
        return patterns
    
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to LangSmith, filtering out unwanted spans and optionally restructuring the trace."""
        logger.info(f"ModifyingSpanExporter.export() called with {len(spans)} span(s)")
        
        # Step 1: Identify which spans to filter
        filtered_span_ids = set()
        spans_to_keep = []
        
        for span in spans:
            if should_filter_span(span, self.filter_patterns):
                filtered_span_ids.add(span.context.span_id)
                logger.debug(f"Marking span for filtering: name={span.name}, span_id={span.context.span_id:x}")
            else:
                spans_to_keep.append(span)
                logger.debug(f"Keeping span: name={span.name}, span_id={span.context.span_id:x}")
        
        if not filtered_span_ids:
            # No filtering needed, export as-is
            logger.info(f"Exporting {len(spans_to_keep)} span(s) to LangSmith")
            return self._export_spans(spans_to_keep)
        
        # Check if reparenting is enabled
        reparent_enabled = os.getenv("OTEL_SPAN_REPARENT_ENABLED", "true").lower() in ("true", "1", "yes")
        
        if not reparent_enabled:
            # Step 2a: Filter out descendants of filtered spans (no reparenting)
            logger.info(f"Reparenting disabled. Filtering out {len(filtered_span_ids)} span(s) and their descendants...")
            
            # Build parent map to find descendants
            parent_map: Dict[int, int] = {}  # child_span_id -> parent_span_id
            span_by_id: Dict[int, ReadableSpan] = {}
            
            for span in spans:
                span_id = span.context.span_id
                span_by_id[span_id] = span
                parent_context = span.parent
                if parent_context and parent_context.span_id:
                    parent_map[span_id] = parent_context.span_id
            
            # Find all descendants of filtered spans
            descendants_to_filter = set(filtered_span_ids)
            for span_id in filtered_span_ids:
                # Find all children (spans whose parent is this filtered span)
                for child_id, parent_id in parent_map.items():
                    if parent_id == span_id:
                        # Recursively add all descendants
                        descendants_to_filter.add(child_id)
                        # Find children of this child
                        stack = [child_id]
                        while stack:
                            current_id = stack.pop()
                            for cid, pid in parent_map.items():
                                if pid == current_id and cid not in descendants_to_filter:
                                    descendants_to_filter.add(cid)
                                    stack.append(cid)
            
            # Filter out all descendants
            final_spans = []
            for span in spans_to_keep:
                if span.context.span_id not in descendants_to_filter:
                    final_spans.append(span)
                else:
                    logger.debug(f"Filtering out descendant: name={span.name}, span_id={span.context.span_id:x}")
            
            filtered_count = len(filtered_span_ids) + len(descendants_to_filter - filtered_span_ids)
            logger.info(f"Filtered out {filtered_count} span(s) (including {len(descendants_to_filter - filtered_span_ids)} descendants), exporting {len(final_spans)} span(s) to LangSmith")
            return self._export_spans(final_spans)
        
        # Step 2b: Restructure trace by reparenting spans whose parents were filtered
        # Pass ALL spans (including filtered) to build complete parent map
        logger.info(f"Reparenting enabled. Filtered out {len(filtered_span_ids)} span(s), restructuring trace...")
        restructured_spans = restructure_trace_spans(spans, spans_to_keep, filtered_span_ids)
        
        logger.info(f"Exporting {len(restructured_spans)} restructured span(s) to LangSmith")
        return self._export_spans(restructured_spans)
    
    def _export_spans(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Internal method to export spans to LangSmith."""
        
        try:
            result = self.base_exporter.export(spans)
            if result == SpanExportResult.SUCCESS:
                logger.info("Successfully exported spans to LangSmith")
            elif result == SpanExportResult.FAILURE:
                logger.error("Failed to export spans to LangSmith")
            return result
        except Exception as e:
            logger.error(f"Exception during span export: {e}", exc_info=True)
            return SpanExportResult.FAILURE
    
    def shutdown(self):
        """Shutdown the exporter."""
        return self.base_exporter.shutdown()
    
    def force_flush(self, timeout_millis: int = 30000):
        """Force flush the exporter."""
        return self.base_exporter.force_flush(timeout_millis)
