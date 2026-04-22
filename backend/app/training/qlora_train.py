from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model

model_name = "mistralai/Mistral-7B-v0.1"

tokenizer = AutoTokenizer.from_pretrained(model_name)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    load_in_4bit=True,
    device_map="auto"
)

lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.1,
    task_type="CAUSAL_LM"
)

model = get_peft_model(model, lora_config)

dataset = load_dataset("gsm8k", split="train[:1%]")

def format(example):
    return {
        "text": f"Question: {example['question']}\nAnswer: {example['answer']}"
    }

dataset = dataset.map(format)

training_args = TrainingArguments(
    output_dir="./qlora-output",
    per_device_train_batch_size=2,
    num_train_epochs=1,
    logging_steps=10
)

trainer = Trainer(
    model=model,
    train_dataset=dataset,
    args=training_args
)

trainer.train()