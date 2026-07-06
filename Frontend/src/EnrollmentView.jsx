import { useState, useEffect } from 'react';

const API_BASE_URL = 'http://raspy.local:8000';

export default function EnrollmentView({ onClose }) {
  const [enrollments, setEnrollments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  
  // Upload State
  const [uploadName, setUploadName] = useState('');
  const [files, setFiles] = useState([]);

  // Live Capture State
  const [liveName, setLiveName] = useState('');
  const [liveStep, setLiveStep] = useState(0); // 0: init, 1: front, 2: left, 3: right

  const fetchEnrollments = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/enrollments`);
      const data = await res.json();
      setEnrollments(data.enrolled || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchEnrollments();
  }, []);

  const handleLiveCaptureStep = async (stepName) => {
    if (!liveName) return setMessage('Name is required');
    setLoading(true);
    setMessage(`Capturing ${stepName} angle...`);
    
    const formData = new FormData();
    formData.append('name', liveName);

    try {
      const res = await fetch(`${API_BASE_URL}/enroll/live`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setMessage(`Success: Captured ${stepName} angle!`);
        if (liveStep === 3) {
           setMessage(`Success: Fully enrolled ${liveName}!`);
           setLiveStep(0);
           setLiveName('');
           fetchEnrollments();
        } else {
           setLiveStep(prev => prev + 1);
        }
      } else {
        setMessage(`Error: ${data.detail}`);
      }
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    }
    setLoading(false);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!uploadName || files.length === 0) return setMessage('Name and files are required');
    setLoading(true);
    setMessage(`Uploading ${files.length} photo(s)...`);

    const formData = new FormData();
    formData.append('name', uploadName);
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const res = await fetch(`${API_BASE_URL}/enroll/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setMessage(`Success: ${data.message}`);
        setUploadName('');
        setFiles([]);
        fetchEnrollments();
      } else {
        setMessage(`Error: ${data.detail}`);
      }
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    }
    setLoading(false);
  };

  const handleDelete = async (targetName) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/enrollments/${targetName}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setMessage(`Deleted ${targetName}`);
        fetchEnrollments();
      }
    } catch (e) {
      setMessage(`Error deleting: ${e.message}`);
    }
    setLoading(false);
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={{margin: 0}}>Face Recognition</h2>
        <button onClick={onClose} style={styles.closeBtn}>×</button>
      </div>
      
      {message && <div style={styles.message}>{message}</div>}

      <div style={styles.section}>
        <h3>Enrolled People</h3>
        {enrollments.length === 0 ? (
          <p style={styles.empty}>No faces enrolled yet.</p>
        ) : (
          <ul style={styles.list}>
            {enrollments.map(person => (
              <li key={person} style={styles.listItem}>
                <span>{person}</span>
                <button 
                  onClick={() => handleDelete(person)}
                  disabled={loading}
                  style={styles.deleteBtn}
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div style={styles.formsContainer}>
        <div style={styles.card}>
          <h3>Guided Multi-Angle Capture</h3>
          <p style={{fontSize: '0.85rem', color: '#888'}}>
            Capture multiple angles of a person's face using the smart glasses for high accuracy.
          </p>
          
          {liveStep === 0 && (
            <div style={styles.form}>
              <input 
                type="text" 
                placeholder="Person's Name" 
                value={liveName} 
                onChange={e => setLiveName(e.target.value)}
                style={styles.input}
              />
              <button 
                onClick={() => setLiveStep(1)} 
                disabled={!liveName} 
                style={styles.primaryBtn}
              >
                Start 3D Capture
              </button>
            </div>
          )}

          {liveStep === 1 && (
            <div style={styles.stepBox}>
              <h4>Step 1: Front Face</h4>
              <p>Look straight at the smart glasses camera.</p>
              <button onClick={() => handleLiveCaptureStep('Front')} disabled={loading} style={styles.primaryBtn}>
                Capture Front
              </button>
            </div>
          )}
          
          {liveStep === 2 && (
            <div style={styles.stepBox}>
              <h4>Step 2: Turn Left</h4>
              <p>Turn your head slightly to the left.</p>
              <button onClick={() => handleLiveCaptureStep('Left Profile')} disabled={loading} style={styles.primaryBtn}>
                Capture Left
              </button>
            </div>
          )}

          {liveStep === 3 && (
            <div style={styles.stepBox}>
              <h4>Step 3: Turn Right</h4>
              <p>Turn your head slightly to the right.</p>
              <button onClick={() => handleLiveCaptureStep('Right Profile')} disabled={loading} style={styles.primaryBtn}>
                Capture Right
              </button>
            </div>
          )}
        </div>

        <div style={styles.card}>
          <h3>Add via Photo Upload</h3>
          <p style={{fontSize: '0.85rem', color: '#888'}}>
            Upload multiple clear photos (front, left, right) for better accuracy.
          </p>
          <form onSubmit={handleUpload} style={styles.form}>
            <input 
              type="text" 
              placeholder="Person's Name" 
              value={uploadName} 
              onChange={e => setUploadName(e.target.value)}
              style={styles.input}
            />
            <input 
              type="file" 
              accept="image/*"
              multiple
              onChange={e => setFiles(e.target.files)}
              style={styles.fileInput}
            />
            <button type="submit" disabled={loading || !uploadName || files.length === 0} style={styles.secondaryBtn}>
              Upload {files.length > 0 ? files.length : ''} Photo(s)
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: '#121212',
    color: '#fff',
    zIndex: 100,
    overflowY: 'auto',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #333',
    paddingBottom: '15px',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#fff',
    fontSize: '32px',
    cursor: 'pointer',
    padding: '0 10px',
  },
  message: {
    padding: '12px',
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: '8px',
    textAlign: 'center',
    fontWeight: 'bold',
  },
  section: {
    backgroundColor: '#1E1E1E',
    padding: '20px',
    borderRadius: '12px',
  },
  list: {
    listStyle: 'none',
    padding: 0,
    margin: 0,
  },
  listItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px',
    borderBottom: '1px solid #333',
    fontSize: '1.1rem',
  },
  empty: {
    color: '#888',
    fontStyle: 'italic',
  },
  deleteBtn: {
    backgroundColor: '#ff4444',
    color: '#fff',
    border: 'none',
    padding: '6px 12px',
    borderRadius: '6px',
    cursor: 'pointer',
  },
  formsContainer: {
    display: 'grid',
    gridTemplateColumns: '1fr',
    gap: '20px',
  },
  card: {
    backgroundColor: '#1E1E1E',
    padding: '20px',
    borderRadius: '12px',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    marginTop: '15px',
  },
  input: {
    padding: '12px',
    borderRadius: '8px',
    border: '1px solid #444',
    backgroundColor: '#2A2A2A',
    color: '#fff',
    fontSize: '1rem',
  },
  fileInput: {
    padding: '8px',
    color: '#aaa',
  },
  primaryBtn: {
    backgroundColor: '#4caf50',
    color: '#fff',
    border: 'none',
    padding: '14px',
    borderRadius: '8px',
    fontSize: '1rem',
    fontWeight: 'bold',
    cursor: 'pointer',
  },
  secondaryBtn: {
    backgroundColor: '#2196f3',
    color: '#fff',
    border: 'none',
    padding: '14px',
    borderRadius: '8px',
    fontSize: '1rem',
    fontWeight: 'bold',
    cursor: 'pointer',
  }
};
