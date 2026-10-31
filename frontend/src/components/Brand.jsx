export function BrandMark({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect width="40" height="40" rx="11" fill="#f4f1e9" />
      <path
        d="M12.5 20c0-4.1 3.1-7 7-7 3.6 0 5.3 2.4 7.5 7s3.9 7 7.5 7"
        transform="translate(-6 -3)"
        fill="none"
        stroke="#0b2f26"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
      <path
        d="M27.5 20c0 4.1-3.1 7-7 7-3.6 0-5.3-2.4-7.5-7s-3.9-7-7.5-7"
        transform="translate(6 3)"
        fill="none"
        stroke="#d9891a"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function Wordmark({ light = false }) {
  return (
    <span className={`wordmark ${light ? 'light' : ''}`}>
      <b>Brightloop</b>
      <i>Billing</i>
    </span>
  )
}
