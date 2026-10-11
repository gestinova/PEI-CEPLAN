function createGenerationRetryId(randomUUID) {
  let pending;
  return {
    forPayload(payload) {
      const signature = JSON.stringify(payload);
      if (!pending || pending.signature !== signature) {
        pending = { signature, id: randomUUID() };
      }
      return pending.id;
    },
    confirmSuccess() { pending = undefined; }
  };
}

if (typeof module !== 'undefined') module.exports = createGenerationRetryId;
