/**
 * Uploads.jsx — Upload CSV/Excel + parse + view history
 */

import { useEffect, useRef, useState } from 'react'
import { uploadApi } from '../api/client'
import Layout from '../components/Layout'
import { Upload, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react'

// Values must match the backend ReportSource enum exactly (lowercase!) —
// uppercase values were rejected with 422 once source actually reached the API.
const SOURCE_OPTIONS = [
  { value: 'pos',       label: 'POS (AdvEntPOS / Square / etc.)' },
  { value: 'website',   label: 'Website' },
  { value: 'uber_eats', label: 'Uber Eats' },
  { value: 'doordash',  label: 'DoorDash' },
  { value: 'other',     label: 'Other' },
]

const STATUS_ICON = {
  pending:    <Clock size={15} className="text-gray-400" />,
  processing: <RefreshCw size={15} className="text-blue-400 animate-spin" />,
  completed:  <CheckCircle size={15} className="text-green-500" />,
  failed:     <XCircle size={15} className="text-red-500" />,
  PENDING:    <Clock size={15} className="text-gray-400" />,
  PROCESSING: <RefreshCw size={15} className="text-blue-400 animate-spin" />,
  COMPLETED:  <CheckCircle size={15} className="text-green-500" />,
  FAILED:     <XCircle size={15} className="text-red-500" />,
}

export default function Uploads() {
  const fileRef = useRef()
  const [source, setSource] = useState('pos')
  const [uploads, setUploads] = useState([])
  const [uploading, setUploading] = useState(false)
  const [parsing, setParsing] = useState({})
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadUploads = async () => {
    try {
      const { data } = await uploadApi.list()
      setUploads(data)
    } catch {
      // ignore
    }
  }

  useEffect(() => { loadUploads() }, [])

  const handleUpload = async (e) => {
    e.preventDefault()
    const file = fileRef.current?.files[0]
    if (!file) return
    setError('')
    setSuccess('')
    setUploading(true)
    try {
      await uploadApi.upload(file, source)
      setSuccess('File uploaded successfully! Click Parse to process it.')
      fileRef.current.value = ''
      loadUploads()
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const handleParse = async (id) => {
    setParsing((p) => ({ ...p, [id]: true }))
    try {
      await uploadApi.parse(id)
      await loadUploads()
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Parse failed.')
    } finally {
      setParsing((p) => ({ ...p, [id]: false }))
    }
  }

  return (
    <Layout>
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Uploads</h1>
        <p className="text-sm text-gray-500 mb-8">Upload CSV or Excel reports from your POS or delivery platforms</p>

        {/* Upload form */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-8">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Upload a report</h2>
          {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}
          {success && <div className="mb-4 p-3 rounded-xl bg-green-50 text-green-700 text-sm">{success}</div>}
          <form onSubmit={handleUpload} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Report source</label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {SOURCE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">File (.csv, .xlsx, .xls)</label>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                required
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:bg-brand-50 file:text-brand-600 file:text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={uploading}
              className="flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60"
            >
              <Upload size={16} />
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
          </form>
        </div>

        {/* Upload history */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Upload history</h2>
          {uploads.length === 0 ? (
            <p className="text-gray-400 text-sm">No uploads yet.</p>
          ) : (
            <div className="space-y-3">
              {uploads.map((u) => (
                <div key={u.id} className="flex items-center justify-between p-4 rounded-xl border border-gray-100 hover:bg-gray-50">
                  <div className="flex items-center gap-3 min-w-0">
                    {STATUS_ICON[u.status] ?? <Clock size={15} />}
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{u.original_filename}</p>
                      <p className="text-xs text-gray-400">
                        {u.source} · {u.rows_processed != null ? `${u.rows_processed} rows` : u.status}
                        {u.error_message && ` · ${u.error_message}`}
                      </p>
                    </div>
                  </div>
                  {u.status?.toUpperCase() === 'PENDING' && (
                    <button
                      onClick={() => handleParse(u.id)}
                      disabled={parsing[u.id]}
                      className="ml-4 shrink-0 bg-brand-50 text-brand-600 hover:bg-brand-100 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors disabled:opacity-60"
                    >
                      {parsing[u.id] ? 'Parsing…' : 'Parse'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
