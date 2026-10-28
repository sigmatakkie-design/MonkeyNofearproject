namespace MonkeyNoFear.Interaction
{
    /// <summary>Anything controlled by physical buttons or levers. Commands are plain strings so the
    /// editor builder can wire controls to machines without UnityEvent plumbing.</summary>
    public interface IButtonReceiver
    {
        void OnButton(string command);
    }
}
