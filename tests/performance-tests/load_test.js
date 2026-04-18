import http from 'k6/http';
import { check, sleep } from 'k6';

const API_GATEWAY_URL = __ENV.API_GATEWAY_URL || 'http://localhost:18000';
const AUTH_URL = __ENV.AUTH_URL || 'http://localhost:18100';
const TEST_PROFILE = __ENV.K6_PROFILE || 'smoke';
const TOKEN_ISSUER_ADMIN_KEY = (__ENV.TOKEN_ISSUER_ADMIN_KEY || '').trim() || 'issuer-admin-key';
const K6_SUMMARY_PATH = (__ENV.K6_SUMMARY_PATH || '').trim();

const profiles = {
  smoke: {
    vus: 5,
    duration: '30s',
    paymentRateP95: 500,
  },
  sustained: {
    vus: 25,
    duration: '2m',
    paymentRateP95: 300,
  },
};

const profile = profiles[TEST_PROFILE] || profiles.smoke;

export const options = {
  vus: profile.vus,
  duration: profile.duration,
  thresholds: {
    'http_req_failed{endpoint:payments}': ['rate<0.01'],
    'http_req_duration{endpoint:payments}': [`p(95)<${profile.paymentRateP95}`],
    checks: ['rate>0.99'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(95)', 'p(99)', 'max'],
};

export function handleSummary(data) {
  const summary = JSON.stringify(data, null, 2);

  if (K6_SUMMARY_PATH) {
    return {
      [K6_SUMMARY_PATH]: summary,
      stdout: summary,
    };
  }

  return { stdout: summary };
}

function issueToken(subject) {
  const response = http.post(
    `${AUTH_URL}/v1/token`,
    JSON.stringify({
      subject,
      expires_in_seconds: 3600,
    }),
    {
      headers: {
        'Content-Type': 'application/json',
        'X-Token-Issuer-Key': TOKEN_ISSUER_ADMIN_KEY,
      },
      tags: { endpoint: 'auth' },
    }
  );

  check(response, {
    'auth token issued': (r) => r.status === 200,
  });

  return response.json('access_token');
}

export default function () {
  const subject = `k6-user-${__VU}-${__ITER}`;
  const accessToken = issueToken(subject);
  const txnId = `k6-${__VU}-${__ITER}-${Date.now()}`;
  const payload = {
    txn_id: txnId,
    user_id: subject,
    idempotency_key: `idem-${txnId}`,
    amount: 42.5,
    currency: 'USD',
    payment_type: 'credit',
    merchant_id: 'merchant-demo',
    lat_lon: [41.8781, -87.6298],
    ip_address: '198.51.100.90',
  };

  const response = http.post(`${API_GATEWAY_URL}/v1/payments`, JSON.stringify(payload), {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    tags: { endpoint: 'payments' },
  });

  check(response, {
    'payment accepted': (r) => r.status === 200,
    'payment queued': (r) => r.json('processing_stage') === 'queued',
    'trace id returned': (r) => typeof r.json('trace_id') === 'string',
  });

  sleep(1);
}
