(function () {
  const normalizeBase = window.normalizeLogRecord;
  const extractTokenUsageBase = window.extractTokenUsage;

  const removedApplicationEvents = new Set([
    'decide',
    'agent_decide',
    'act',
    'agent_action',
    'llm_cli_call',
  ]);

  if (typeof normalizeBase === 'function') {
    window.normalizeLogRecord = function normalizeApplicationEvent(record, origin) {
      const normalized = normalizeBase(record, origin);
      if (!normalized) return normalized;

      const event = record?.event || '';
      if (event === 'reasoning' || event === 'acting') {
        normalized.field = 'agent';
      } else if (event === 'llm_api_call') {
        normalized.field = 'llm_api';
      } else if (removedApplicationEvents.has(event)) {
        normalized.field = 'system';
        normalized.level = 'ERROR';
        normalized.eventText = `Unsupported application event: ${event}`;
        normalized.detailText = '';
      }
      return normalized;
    };
  }

  if (typeof extractTokenUsageBase === 'function') {
    window.extractTokenUsage = function extractApiTokenUsage(record) {
      if (!record || record.event !== 'llm_api_call') return null;
      return extractTokenUsageBase(record);
    };
  }
})();
