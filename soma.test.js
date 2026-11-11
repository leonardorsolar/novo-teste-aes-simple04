const { test } = require('node:test');
const assert = require('node:assert/strict');
const { soma } = require('./soma.js');

test('soma(5, 10) retorna 15', () => {
  assert.equal(soma(5, 10), 15);
});

test('soma com zero', () => {
  assert.equal(soma(0, 0), 0);
  assert.equal(soma(0, 7), 7);
  assert.equal(soma(7, 0), 7);
});

test('soma com negativos', () => {
  assert.equal(soma(-3, -4), -7);
  assert.equal(soma(-3, 10), 7);
});

test('soma de decimais com tolerância', () => {
  const r = soma(0.1, 0.2);
  assert.ok(Math.abs(r - 0.3) < 1e-9);
});
