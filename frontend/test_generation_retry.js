const assert = require('node:assert');
const createGenerationRetryId = require('./generation_retry');

let sequence = 0;
const retry = createGenerationRetryId(() => `id-${++sequence}`);
assert.equal(retry.forPayload({ municipality: 'A' }), 'id-1');
assert.equal(retry.forPayload({ municipality: 'A' }), 'id-1');
assert.equal(retry.forPayload({ municipality: 'B' }), 'id-2');
retry.confirmSuccess();
assert.equal(retry.forPayload({ municipality: 'B' }), 'id-3');
