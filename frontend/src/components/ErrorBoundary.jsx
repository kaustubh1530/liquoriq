/**
 * ErrorBoundary.jsx — never show a blank white page again.
 *
 * A render-time exception anywhere in the tree unmounts the whole React app,
 * which looks to the user like "the page is broken" with zero information. This
 * catches it, shows what actually failed, and keeps the rest of the app usable.
 */

import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Keep the full stack in the console for debugging
    console.error('[LiquorIQ] render error:', error, info)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="max-w-xl mx-auto mt-10 bg-white border border-red-100 rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-3 text-red-600">
          <AlertTriangle size={18} />
          <h2 className="font-semibold text-sm">{this.props.title || 'Something broke on this page'}</h2>
        </div>
        <p className="text-sm text-gray-600 mb-3">
          The rest of LiquorIQ still works — use the sidebar to move on. If this keeps
          happening, the message below is what to report.
        </p>
        <pre className="text-[11px] bg-gray-50 rounded-lg p-3 overflow-auto max-h-48 text-gray-700">
          {String(error?.message || error)}
        </pre>
        <button
          onClick={() => this.setState({ error: null })}
          className="mt-3 text-xs font-semibold text-brand-500 hover:underline"
        >
          Try again
        </button>
      </div>
    )
  }
}
