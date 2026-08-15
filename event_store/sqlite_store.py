def read_stream(self, stream_id: str) -> Tuple[BaseOrderEvent, ...]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT event_type, schema_version, payload, payload_hash 
                FROM order_events 
                WHERE stream_id = ? 
                ORDER BY stream_version ASC
                """,
                (stream_id,)
            )
            rows = cursor.fetchall()

        events = []
        for event_type, schema_version, payload, payload_hash in rows:
            # Delegate integrity and deserialization to the hardened EventSerializer
            event = EventSerializer.deserialize(event_type, schema_version, payload, payload_hash)
            events.append(event)

        return tuple(events)
