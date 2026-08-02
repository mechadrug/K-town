package agent

import (
	"container/ring"
	"sort"
	"time"
)

// MemoryEntry stores a single long-term memory
type MemoryEntry struct {
	ID          string
	Description string
	Importance  float64
	Timestamp   time.Time
	Tags        []string
}

// DiaryEntry is a daily summary written by the agent
type DiaryEntry struct {
	Date       time.Time
	Summary    string
	Highlights []string
}

// MemorySystem holds short-term, long-term and diary memory
type MemorySystem struct {
	ShortTerm *ring.Ring
	LongTerm  []MemoryEntry
	Diary     []DiaryEntry
	MaxSize   int
}

// NewMemorySystem creates a memory system with default short-term size
func NewMemorySystem() *MemorySystem {
	return &MemorySystem{
		ShortTerm: ring.New(20),
		LongTerm:  []MemoryEntry{},
		Diary:     []DiaryEntry{},
		MaxSize:   20,
	}
}

// Observation is a raw event an agent perceives
type Observation struct {
	Description string
	Timestamp   time.Time
	Importance  float64
}

// AddObservation records an observation into short-term memory
func (m *MemorySystem) AddObservation(desc string, importance float64) {
	m.ShortTerm.Value = Observation{
		Description: desc,
		Timestamp:   time.Now(),
		Importance:  importance,
	}
	m.ShortTerm = m.ShortTerm.Next()
}

// Consolidate moves important short-term observations into long-term memory
func (m *MemorySystem) Consolidate(threshold float64) {
	m.ShortTerm.Do(func(v interface{}) {
		if v == nil {
			return
		}
		obs, ok := v.(Observation)
		if !ok {
			return
		}
		if obs.Importance >= threshold {
			m.LongTerm = append(m.LongTerm, MemoryEntry{
				ID:          generateID(),
				Description: obs.Description,
				Importance:  obs.Importance,
				Timestamp:   obs.Timestamp,
			})
		}
	})
	sort.Slice(m.LongTerm, func(i, j int) bool {
		return m.LongTerm[i].Importance > m.LongTerm[j].Importance
	})
}

// WriteDiary creates a daily diary entry
func (m *MemorySystem) WriteDiary(summary string, highlights []string) {
	m.Diary = append(m.Diary, DiaryEntry{
		Date:       time.Now(),
		Summary:    summary,
		Highlights: highlights,
	})
}

// RecentObservations returns the short-term entries as a slice
func (m *MemorySystem) RecentObservations() []Observation {
	var result []Observation
	m.ShortTerm.Do(func(v interface{}) {
		if v != nil {
			if obs, ok := v.(Observation); ok {
				result = append(result, obs)
			}
		}
	})
	return result
}

// LongTermTopN returns the N most important long-term memories
func (m *MemorySystem) LongTermTopN(n int) []MemoryEntry {
	if n > len(m.LongTerm) {
		n = len(m.LongTerm)
	}
	return m.LongTerm[:n]
}
