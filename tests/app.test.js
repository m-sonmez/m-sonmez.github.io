/* tests/app.test.js – Unit tests for Klinik Dashboard utility functions */
/* ========================================================================== */
import test from 'node:test';
import assert from 'node:assert/strict';

/* Import exported functions from app.js */
import {debounce, formatFullDate, formatTurkishDate, getBPBadgeClass, getBPStatusText, getLabItemStatus} from '../app.js';

/* ========================================================================== */
/* Test Suite: getBPStatusText                                               */
/* ========================================================================== */
test('getBPStatusText – returns correct status for given BP values', () => {
  assert.strictEqual(getBPStatusText(120, 80), 'Normal');
  assert.strictEqual(getBPStatusText(130, 85), 'Prehipertansiyon');
  assert.strictEqual(getBPStatusText(140, 89), 'Hipertansiyon');
  assert.strictEqual(getBPStatusText(139, 90), 'Hipertansiyon');
  assert.strictEqual(getBPStatusText(120, 85), 'Prehipertansiyon');
  assert.strictEqual(getBPStatusText(110, 70), 'Normal');
});

/* ========================================================================== */
/* Test Suite: getBPBadgeClass                                              */
/* ========================================================================== */
test('getBPBadgeClass – returns correct badge class for given BP values', () => {
  /* getBPBadgeClass uses this.getBPStatusText, so we bind it to the exported function */
  const boundGetBPBadgeClass = getBPBadgeClass.bind({
    getBPStatusText: getBPStatusText,
  });

  assert.strictEqual(boundGetBPBadgeClass(120, 80), 'bg-emerald-50 text-emerald-700 border border-emerald-200');
  assert.strictEqual(boundGetBPBadgeClass(130, 85), 'bg-amber-50 text-amber-700 border border-amber-200');
  assert.strictEqual(boundGetBPBadgeClass(140, 89), 'bg-rose-50 text-rose-700 border border-rose-200');
  assert.strictEqual(boundGetBPBadgeClass(139, 90), 'bg-rose-50 text-rose-700 border border-rose-200');
  assert.strictEqual(boundGetBPBadgeClass(120, 85), 'bg-amber-50 text-amber-700 border border-amber-200');
});

/* ========================================================================== */
/* Test Suite: getLabItemStatus                                             */
/* ========================================================================== */
test('getLabItemStatus – returns Normal for missing or invalid input', () => {
  assert.strictEqual(getLabItemStatus(null), 'Normal');
  assert.strictEqual(getLabItemStatus({}), 'Normal');
  assert.strictEqual(getLabItemStatus({result: 'abc'}), 'Normal');
});

test('getLabItemStatus – returns Normal when value is within reference range', () => {
  const item = {
    result: '10.0',
    reference_min: '5.0',
    reference_max: '15.0',
  };
  assert.strictEqual(getLabItemStatus(item), 'Normal');

  /* Edge: equal to min or max */
  assert.strictEqual(getLabItemStatus({...item, result: '5.0'}), 'Normal');
  assert.strictEqual(getLabItemStatus({...item, result: '15.0'}), 'Normal');
});

test('getLabItemStatus – returns Düşük when value is below reference_min', () => {
  const item = {
    result: '4.0',
    reference_min: '5.0',
    reference_max: '15.0',
  };
  assert.strictEqual(getLabItemStatus(item), 'Düşük');
});

test('getLabItemStatus – returns Yüksek when value is above reference_max', () => {
  const item = {
    result: '16.0',
    reference_min: '5.0',
    reference_max: '15.0',
  };
  assert.strictEqual(getLabItemStatus(item), 'Yüksek');
});

test('getLabItemStatus – handles missing reference_min or reference_max gracefully', () => {
  const itemMinMissing = {
    result: '4.0',
    reference_min: null,
    reference_max: '15.0',
  };
  assert.strictEqual(getLabItemStatus(itemMinMissing), 'Normal');

  const itemMaxMissing = {
    result: '16.0',
    reference_min: '5.0',
    reference_max: null,
  };
  assert.strictEqual(getLabItemStatus(itemMaxMissing), 'Normal');
});

/* ========================================================================== */
/* Test Suite: formatTurkishDate                                            */
/* ========================================================================== */
test('formatTurkishDate – formats ISO date string correctly', () => {
  assert.strictEqual(formatTurkishDate('2026-07-25'), '25.07.2026');
  assert.strictEqual(formatTurkishDate('2026-07-25 14:30:00'), '25.07.2026');
  assert.strictEqual(formatTurkishDate('2026-01-01'), '01.01.2026');
});

test('formatTurkishDate – returns "-" for empty input', () => {
  assert.strictEqual(formatTurkishDate(''), '-');
  assert.strictEqual(formatTurkishDate(null), '-');
  assert.strictEqual(formatTurkishDate(undefined), '-');
});

test('formatTurkishDate – returns input unchanged for invalid format', () => {
  assert.strictEqual(formatTurkishDate('invalid-date'), 'invalid-date');
  assert.strictEqual(formatTurkishDate('25.07.2026'), '25.07.2026');
});

/* ========================================================================== */
/* Test Suite: formatFullDate                                               */
/* ========================================================================== */
test('formatFullDate – formats date string correctly', () => {
  assert.strictEqual(formatFullDate('2026-07-25'), '25 Temmuz 2026');
  assert.strictEqual(formatFullDate('2026-01-01'), '1 Ocak 2026');
  assert.strictEqual(formatFullDate('2026-12-31'), '31 Aralık 2026');
});

test('formatFullDate – accepts Date objects', () => {
  const date = new Date(2026, 6, 25); /* month is 0-indexed, so 6 = July */
  assert.strictEqual(formatFullDate(date), '25 Temmuz 2026');
});

test('formatFullDate – returns empty string for invalid input', () => {
  assert.strictEqual(formatFullDate(''), '');
  assert.strictEqual(formatFullDate(null), '');
  assert.strictEqual(formatFullDate(undefined), '');
  assert.strictEqual(formatFullDate('invalid'), '');
});

/* ========================================================================== */
/* Test Suite: debounce                                                     */
/* ========================================================================== */
test('debounce – delays function execution', (t) => {
  /* Use test context to manage timeouts */

  let callCount = 0;
  const fn = () => {
    callCount++;
  };
  const debounced = debounce(fn, 50);

  /* Call multiple times in quick succession */
  debounced();
  debounced();
  debounced();

  /* After 30ms, still not executed */
  return new Promise((resolve) => {
    setTimeout(() => {
      assert.strictEqual(callCount, 0);
      /* After 60ms, should have executed once */
      setTimeout(() => {
        assert.strictEqual(callCount, 1);
        resolve();
      }, 20);
    }, 30);
  });
});

test('debounce – passes arguments correctly', (t) => {
  let lastArgs = null;
  const fn = (...args) => {
    lastArgs = args;
  };
  const debounced = debounce(fn, 50);

  debounced(1, 'a', true);

  return new Promise((resolve) => {
    setTimeout(() => {
      assert.deepStrictEqual(lastArgs, [1, 'a', true]);
      resolve();
    }, 60);
  });
});

test('debounce – preserves `this` context', (t) => {
  const context = {value: 42};
  function fn() {
    /* this should be bound to context */
    return this.value;
  }
  const debounced = debounce.bind(context)(fn, 50);

  let result = null;
  debounced.call(context, (val) => {
    result = val;
  });

  return new Promise((resolve) => {
    setTimeout(() => {
      /* The function itself doesn't return, but we can test side effects */
      /* Instead, test by calling a method that uses this */
      const obj = {
        value: 99,
        method: function (cb) {
          cb(this.value);
        },
      };
      const debouncedMethod = debounce(obj.method, 50).bind(obj);
      let methodResult = null;
      debouncedMethod((val) => {
        methodResult = val;
      });
      setTimeout(() => {
        assert.strictEqual(methodResult, 99);
        resolve();
      }, 60);
    }, 60);
  });
});
