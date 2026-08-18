/**
 * What `echarts-for-react` resolves to under the test runner, and nothing else imports this.
 *
 * echarts draws onto a canvas it measures itself. jsdom lays nothing out and implements no 2D
 * context, so the chart initialises against a 0x0 element and then throws inside its own painter
 * when React unmounts it — a crash in a dependency's teardown, reported against whichever test
 * happened to render a page containing a chart.
 *
 * Stubbing rather than shimming a canvas is the honest option and it follows the rule this suite
 * already runs on: what is asserted here is classification, derivation and structural invariants,
 * never rendered pixels. Every chart's option builder is a pure function tested directly, so the
 * only thing a real echarts adds under jsdom is a fictional layout and a teardown crash.
 *
 * The stub keeps the accessible name, because that is a structural fact a test may reasonably
 * assert and it does not depend on anything being drawn.
 */

export default function EChartsReactStub({
  "aria-label": ariaLabel,
  className,
  style,
}: {
  "aria-label"?: string
  className?: string
  style?: Record<string, unknown>
}) {
  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className={className}
      style={style}
      data-testid="echart-stub"
    />
  )
}
