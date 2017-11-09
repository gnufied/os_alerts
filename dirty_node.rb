require 'json'
require "time"

class DirtyNode
  def initialize(op_name, file_path, profile, region)
    @op_name = op_name.strip()
    @file_path = file_path
    @profile = profile
    @region = region
  end

  def print_dirty_nodes()
    data = File.read(@file_path)
    json_data = JSON.load(data)
    volumes = json_data["Volumes"]
    @dirty_nodes = {}

    volumes.each do |volume|
      if check_attaching_volume(volume)
        attachment = volume["Attachments"][0]
        @dirty_nodes[attachment["InstanceId"]] = volume
      end
    end

    @dirty_nodes.each do |node, val|
      if @op_name == "reboot"
        reboot_node(node)
      else
        puts "Volume stuck on node #{node}"
      end
    end
  end

  def reboot_node(node)
    command = "aws ec2 reboot-instances --instance-ids #{node} --profile=#{@profile} --region=#{@region}"
    puts "Running - #{command}"
    system(command)
  end

  def check_attaching_volume(volume)
    attachments = volume["Attachments"]

    if !attachments.empty?
      attachment = attachments[0]
      attachment_state = attachment["State"]
      instance_id = attachment["InstanceId"]
      volume_id = attachment["VolumeId"]
      if attachment_state == "attaching"
        attach_time_str = attachment["AttachTime"]
        if stuck_in_attaching?(attach_time_str)
          puts "Volume #{volume_id} is stuck to #{instance_id}"
          return true
        end
        false
      else
        false
      end
    else
      false
    end
  end

  def stuck_in_attaching?(attach_time_str)
    attach_time = Time.parse(attach_time_str)
    time_diff = (Time.now() - attach_time)/60
    # if time difference is greater than 30 minutes
    time_diff > 30
  end
end



a = DirtyNode.new(ARGV[0], ARGV[1], ARGV[2], ARGV[3])
a.print_dirty_nodes
