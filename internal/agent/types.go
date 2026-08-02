package agent

import (
	"time"
)

// Role represents an agent's societal function
type Role string

const (
	RoleElder       Role = "elder"
	RoleBlacksmith  Role = "blacksmith"
	RoleCarpenter   Role = "carpenter"
	RoleForager     Role = "forager"
	RoleScout       Role = "scout"
	RoleMerchant    Role = "merchant"
	RoleTeacher     Role = "teacher"
	RoleFarmer      Role = "farmer"
	RoleStoryteller Role = "storyteller"
	RolePlayer      Role = "player"
)

// Mood represents an agent's emotional state
type Mood string

const (
	MoodHappy   Mood = "happy"
	MoodNeutral Mood = "neutral"
	MoodAnxious Mood = "anxious"
	MoodAngry   Mood = "angry"
	MoodSad     Mood = "sad"
)

// SkillName is a typed skill identifier
type SkillName string

// Identity holds stable, long-lived agent properties
type Identity struct {
	ID     string
	Name   string
	Role   Role
	Traits []string
	Skills map[SkillName]int
}

// Item represents a single inventory item
type Item struct {
	ID     string
	Name   string
	Weight float64
}

// Task describes what an agent is currently doing
type Task struct {
	Description string
	Location    string
	StartedAt   time.Time
}

// State holds dynamic, tick-varying agent properties
type State struct {
	Energy      float64
	Mood        Mood
	Gold        int
	Location    string
	CurrentTask *Task
	Inventory   []Item
	SocialTies  map[string]float64
}

// Agent combines identity, state, memory, knowledge, goals and schedule
type Agent struct {
	Identity  Identity
	State     State
	Memory    *MemorySystem
	Knowledge []*KnowledgeClaim
	Goals     []*Goal
	Schedule  *Schedule
}

// KnowledgeClaim represents a piece of knowledge held by an agent
type KnowledgeClaim struct {
	ID         string
	Content    string
	Confidence float64
	Source     string
	Timestamp  time.Time
}

// NewIdentity creates an identity with initialized maps
func NewIdentity(id, name string, role Role) Identity {
	return Identity{
		ID:     id,
		Name:   name,
		Role:   role,
		Traits: []string{},
		Skills: make(map[SkillName]int),
	}
}

// NewState creates a default state for an agent
func NewState() State {
	return State{
		Energy:      100,
		Mood:        MoodNeutral,
		Gold:        0,
		Location:    "",
		CurrentTask: nil,
		Inventory:   []Item{},
		SocialTies:  make(map[string]float64),
	}
}

// NewAgent constructs an Agent from identity and schedule
func NewAgent(identity Identity, schedule *Schedule) *Agent {
	return &Agent{
		Identity:  identity,
		State:     NewState(),
		Memory:    NewMemorySystem(),
		Knowledge: []*KnowledgeClaim{},
		Goals:     []*Goal{},
		Schedule:  schedule,
	}
}
