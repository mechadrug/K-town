package log

import (
	"sync"
)

// WorldEventRecord logs a world-level event.
type WorldEventRecord struct {
	Tick      int64                  `json:"tick"`
	EventType string                 `json:"event_type"`
	Location  string                 `json:"location"`
	Actors    []string               `json:"actors"`
	Payload   map[string]interface{} `json:"payload"`
	Timestamp int64                  `json:"timestamp"`
}

// DecisionRecord logs an agent decision.
type DecisionRecord struct {
	Tick       int64   `json:"tick"`
	AgentID    string  `json:"agent_id"`
	Action     string  `json:"action"`
	Reason     string  `json:"reason"`
	Goal       string  `json:"goal"`
	Confidence float64 `json:"confidence"`
	Method     string  `json:"method"`
}

// KnowledgeRecord logs a knowledge operation.
type KnowledgeRecord struct {
	Tick      int64  `json:"tick"`
	ClaimID   string `json:"claim_id"`
	AgentID   string `json:"agent_id"`
	Operation string `json:"operation"`
	Before    string `json:"before"`
	After     string `json:"after"`
}

// DefaultBufferSize is the default ring buffer capacity.
const DefaultBufferSize = 1000

// Logger holds ring buffers for world events, decisions, and knowledge records.
type Logger struct {
	worldBuf     []WorldEventRecord
	decisionBuf  []DecisionRecord
	knowledgeBuf []KnowledgeRecord
	worldIdx     int
	decisionIdx  int
	knowledgeIdx int
	worldCount   int
	decisionCount int
	knowledgeCount int
	mu           sync.RWMutex
}

// New creates a new Logger with default buffer sizes.
func New() *Logger {
	return NewWithSize(DefaultBufferSize)
}

// NewWithSize creates a new Logger with a custom buffer size.
func NewWithSize(size int) *Logger {
	return &Logger{
		worldBuf:     make([]WorldEventRecord, size),
		decisionBuf:  make([]DecisionRecord, size),
		knowledgeBuf: make([]KnowledgeRecord, size),
	}
}

// LogWorldEvent records a world event.
func (l *Logger) LogWorldEvent(r WorldEventRecord) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.worldBuf[l.worldIdx] = r
	l.worldIdx = (l.worldIdx + 1) % len(l.worldBuf)
	if l.worldCount < len(l.worldBuf) {
		l.worldCount++
	}
}

// LogDecision records an agent decision.
func (l *Logger) LogDecision(r DecisionRecord) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.decisionBuf[l.decisionIdx] = r
	l.decisionIdx = (l.decisionIdx + 1) % len(l.decisionBuf)
	if l.decisionCount < len(l.decisionBuf) {
		l.decisionCount++
	}
}

// LogKnowledge records a knowledge operation.
func (l *Logger) LogKnowledge(r KnowledgeRecord) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.knowledgeBuf[l.knowledgeIdx] = r
	l.knowledgeIdx = (l.knowledgeIdx + 1) % len(l.knowledgeBuf)
	if l.knowledgeCount < len(l.knowledgeBuf) {
		l.knowledgeCount++
	}
}

// QueryWorldEvents returns the most recent n world events (or all if n <= 0).
func (l *Logger) QueryWorldEvents(n int) []WorldEventRecord {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.extractWorld(n)
}

// QueryDecisions returns the most recent n decisions (or all if n <= 0).
func (l *Logger) QueryDecisions(n int) []DecisionRecord {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.extractDecisions(n)
}

// QueryKnowledge returns the most recent n knowledge records (or all if n <= 0).
func (l *Logger) QueryKnowledge(n int) []KnowledgeRecord {
	l.mu.RLock()
	defer l.mu.RUnlock()
	return l.extractKnowledge(n)
}

// extractWorld returns the last n world events in chronological order.
func (l *Logger) extractWorld(n int) []WorldEventRecord {
	count := l.worldCount
	if n > 0 && n < count {
		count = n
	}
	result := make([]WorldEventRecord, count)
	size := len(l.worldBuf)
	for i := 0; i < count; i++ {
		idx := (l.worldIdx - count + i + size) % size
		result[i] = l.worldBuf[idx]
	}
	return result
}

// extractDecisions returns the last n decisions in chronological order.
func (l *Logger) extractDecisions(n int) []DecisionRecord {
	count := l.decisionCount
	if n > 0 && n < count {
		count = n
	}
	result := make([]DecisionRecord, count)
	size := len(l.decisionBuf)
	for i := 0; i < count; i++ {
		idx := (l.decisionIdx - count + i + size) % size
		result[i] = l.decisionBuf[idx]
	}
	return result
}

// extractKnowledge returns the last n knowledge records in chronological order.
func (l *Logger) extractKnowledge(n int) []KnowledgeRecord {
	count := l.knowledgeCount
	if n > 0 && n < count {
		count = n
	}
	result := make([]KnowledgeRecord, count)
	size := len(l.knowledgeBuf)
	for i := 0; i < count; i++ {
		idx := (l.knowledgeIdx - count + i + size) % size
		result[i] = l.knowledgeBuf[idx]
	}
	return result
}
