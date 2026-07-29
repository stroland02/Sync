// The same ending, with the module explaining itself on stderr first. That last line is the
// only account of why nothing ran, so it is what the reason has to carry to an operator.
console.error('billing.ts: BILLING_CONFIG is not set');
process.exit(78);

export async function charge(amount: number) {
  return { id: 'unreachable' };
}
